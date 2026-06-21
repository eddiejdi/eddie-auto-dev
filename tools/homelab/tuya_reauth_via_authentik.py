#!/usr/bin/env python3
"""Reauthenticate Home Assistant Tuya and persist state directly in Authentik.

This helper runs from the workstation and uses SSH to the `homelab` host.
It does not depend on the Secrets Agent. The flow is:

1. Read the current Tuya config entry from Home Assistant.
2. Ask Tuya for a fresh QR login token.
3. Render a local QR image for the user to scan in Smart Life / Tuya Smart.
4. Poll Tuya until the scan/login succeeds.
5. Validate the new token with the Tuya SDK inside the Home Assistant container.
6. Update `/config/.storage/core.config_entries`.
7. Mirror static Tuya fields plus `token_info_json` directly to Authentik.
8. Restart Home Assistant and print a compact validation summary.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

import qrcode


def _run(cmd: list[str], *, input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _ssh(host: str, command: str, *, input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return _run(
        ["ssh", "-o", "BatchMode=yes", host, command],
        input_text=input_text,
        timeout=timeout,
    )


def _ssh_python(host: str, script: str, *, timeout: int = 60, sudo: bool = False) -> dict:
    command = "sudo python3 -" if sudo else "python3 -"
    proc = _ssh(host, command, input_text=script, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"remote python failed rc={proc.returncode}: {proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


def _ssh_ha_python(host: str, script: str, *, timeout: int = 60) -> dict:
    proc = _ssh(host, "docker exec -i homeassistant python3 -", input_text=script, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"remote HA python failed rc={proc.returncode}: {proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


def issue_qr(host: str) -> dict:
    script = """
import json
import pathlib
from tuya_sharing import LoginControl
from homeassistant.components.tuya.const import TUYA_CLIENT_ID, TUYA_SCHEMA

cfg = json.loads(pathlib.Path("/config/.storage/core.config_entries").read_text())
entry = next(e for e in cfg["data"]["entries"] if e.get("domain") == "tuya")
user_code = entry["data"]["user_code"]
resp = LoginControl().qr_code(TUYA_CLIENT_ID, TUYA_SCHEMA, user_code)
print(json.dumps({
    "entry_id": entry["entry_id"],
    "title": entry["title"],
    "user_code": user_code,
    "client_id": TUYA_CLIENT_ID,
    "schema": TUYA_SCHEMA,
    "response": resp,
}, ensure_ascii=False))
"""
    return _ssh_ha_python(host, script, timeout=60)


def save_qr(token: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    out = output_dir / f"tuya_reauth_qr_{stamp}.png"
    qrcode.make(f"tuyaSmart--qrLogin?token={token}").save(out)
    return out


def poll_login(host: str, *, token: str, client_id: str, user_code: str, timeout_s: int, interval_s: int) -> dict:
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        script = f"""
import json
from tuya_sharing import LoginControl
ok, info = LoginControl().login_result({token!r}, {client_id!r}, {user_code!r})
print(json.dumps({{"attempt": {attempt}, "ok": ok, "info": info}}, ensure_ascii=False))
"""
        result = _ssh_ha_python(host, script, timeout=60)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result.get("ok"):
            return result["info"]
        time.sleep(interval_s)
    raise TimeoutError(f"Tuya QR login timed out after {timeout_s}s")


def apply_and_persist(host: str, *, entry_id: str, user_code: str, login_info: dict) -> dict:
    payload = json.dumps(
        {
            "entry_id": entry_id,
            "user_code": user_code,
            "login_info": login_info,
            "modified_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=True,
    )
    script = f"""
import json
import pathlib
import subprocess
import time

payload = json.loads({payload!r})
storage = pathlib.Path("/home/homelab/homeassistant/config/.storage/core.config_entries")
cfg = json.loads(storage.read_text())
entry = next(e for e in cfg["data"]["entries"] if e.get("entry_id") == payload["entry_id"])
backup = storage.with_name(storage.name + ".tuya-reauth-" + str(int(time.time())) + ".bak")
backup.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

info = payload["login_info"]
entry["title"] = info.get("username", entry.get("title"))
entry["modified_at"] = payload["modified_at"]
entry["data"] = {{
    "user_code": payload["user_code"],
    "token_info": {{
        "t": info["t"],
        "uid": info["uid"],
        "expire_time": info["expire_time"],
        "access_token": info["access_token"],
        "refresh_token": info["refresh_token"],
    }},
    "terminal_id": info["terminal_id"],
    "endpoint": info["endpoint"],
}}
storage.write_text(json.dumps(cfg, ensure_ascii=False, separators=(",", ":")))

token_info_json = json.dumps(entry["data"]["token_info"], ensure_ascii=True, separators=(",", ":"))
records = [
    {{
        "client_id": "secret-smartlife-tuya-username",
        "name": "Secret Holder - shared/smartlife_tuya_account#username",
        "value": entry["title"],
    }},
    {{
        "client_id": "secret-smartlife-tuya-endpoint",
        "name": "Secret Holder - shared/smartlife_tuya_account#endpoint",
        "value": entry["data"]["endpoint"],
    }},
    {{
        "client_id": "secret-smartlife-tuya-user-code",
        "name": "Secret Holder - shared/smartlife_tuya_account#user_code",
        "value": entry["data"]["user_code"],
    }},
    {{
        "client_id": "secret-smartlife-tuya-ha-entry-id",
        "name": "Secret Holder - shared/smartlife_tuya_account#ha_config_entry_id",
        "value": entry["entry_id"],
    }},
    {{
        "client_id": "secret-smartlife-tuya-token-info-json",
        "name": "Secret Holder - shared/smartlife_tuya_account#token_info_json",
        "value": token_info_json,
    }},
]
records_json = json.dumps(records, ensure_ascii=True)

ak_code = '''
import json
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, RedirectURI, RedirectURIMatchingMode

records = json.loads(__AK_RECORDS_JSON__)
flow = Flow.objects.filter(designation="authorization").order_by("slug").first()
if flow is None:
    raise RuntimeError("authorization flow not found")

results = []
for rec in records:
    provider, created = OAuth2Provider.objects.update_or_create(
        client_id=rec["client_id"],
        defaults={{
            "name": rec["name"],
            "authorization_flow": flow,
            "client_type": "confidential",
            "client_secret": rec["value"],
            "redirect_uris": [
                RedirectURI(
                    RedirectURIMatchingMode.STRICT,
                    "https://example.local/authentik-secret-holder",
                )
            ],
            "sub_mode": "hashed_user_id",
            "issuer_mode": "per_provider",
            "include_claims_in_id_token": False,
        }},
    )
    provider.save()
    results.append({{
        "client_id": rec["client_id"],
        "created": created,
        "secret_len": len(rec["value"]),
    }})
print("AUTHENTIK_RESULT=" + json.dumps(results, sort_keys=True))
'''.replace("__AK_RECORDS_JSON__", repr(records_json))
ak = subprocess.run(
    ["docker", "exec", "authentik-server", "ak", "shell", "-c", ak_code],
    text=True,
    capture_output=True,
    check=False,
    timeout=180,
)
marker = "AUTHENTIK_RESULT="
authentik_line = next((line for line in ak.stdout.splitlines() if line.startswith(marker)), None)

restart = subprocess.run(["sudo", "docker", "restart", "homeassistant"], text=True, capture_output=True, check=False, timeout=120)
time.sleep(20)

validate = subprocess.run(
    ["docker", "exec", "homeassistant", "python3", "-c", '''
import json, pathlib
from tuya_sharing.manager import Manager
from homeassistant.components.tuya.const import TUYA_CLIENT_ID
cfg = json.loads(pathlib.Path('/config/.storage/core.config_entries').read_text())
entry = next(e for e in cfg['data']['entries'] if e.get('domain') == 'tuya')
class Listener:
    def update_token(self, token_info):
        pass
manager = Manager(TUYA_CLIENT_ID, entry['data']['user_code'], entry['data']['terminal_id'], entry['data']['endpoint'], entry['data']['token_info'], Listener())
manager.update_device_cache()
print(json.dumps({{"homes": len(manager.user_homes), "devices": len(manager.device_map)}}))
'''],
    text=True,
    capture_output=True,
    check=False,
    timeout=180,
)

summary = subprocess.run(
    ["python3", "-c", '''
import json, sqlite3
db = '/home/homelab/homeassistant/config/home-assistant_v2.db'
q = (
    "WITH latest AS ("
    " SELECT metadata_id, max(state_id) AS max_state_id"
    " FROM states"
    " GROUP BY metadata_id"
    ") "
    "SELECT substr(sm.entity_id,1,instr(sm.entity_id,'.')-1) AS domain,"
    " count(*) AS total,"
    " sum(case when s.state='unavailable' then 1 else 0 end) AS unavailable"
    " FROM latest l"
    " JOIN states s ON s.state_id=l.max_state_id"
    " JOIN states_meta sm ON sm.metadata_id=s.metadata_id"
    " WHERE sm.entity_id GLOB 'switch.*'"
    " OR sm.entity_id GLOB 'light.*'"
    " OR sm.entity_id GLOB 'fan.*'"
    " OR sm.entity_id GLOB 'remote.*'"
    " GROUP BY domain"
    " ORDER BY domain"
)
conn = sqlite3.connect(db)
rows = [dict(zip(['domain','total','unavailable'], row)) for row in conn.execute(q)]
print(json.dumps(rows))
'''],
    text=True,
    capture_output=True,
    check=False,
    timeout=120,
)

print(json.dumps({{
    "backup_path": str(backup),
    "authentik_rc": ak.returncode,
    "authentik_result": json.loads(authentik_line[len(marker):]) if authentik_line else None,
    "authentik_stderr_tail": ak.stderr.splitlines()[-10:],
    "restart_rc": restart.returncode,
    "restart_stdout": restart.stdout.strip(),
    "validate_rc": validate.returncode,
    "validate_stdout": validate.stdout.strip(),
    "validate_stderr": validate.stderr.strip(),
    "state_summary": json.loads(summary.stdout) if summary.returncode == 0 and summary.stdout.strip() else None,
}}, ensure_ascii=False))
"""
    return _ssh_python(host, script, timeout=420, sudo=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="homelab")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Local directory for the QR image.",
    )
    args = parser.parse_args()

    issued = issue_qr(args.host)
    if not issued["response"].get("success"):
        print(json.dumps(issued, ensure_ascii=False), file=sys.stderr)
        return 1

    qr_token = issued["response"]["result"]["qrcode"]
    qr_path = save_qr(qr_token, Path(args.output_dir))
    print(json.dumps({
        "status": "qr_ready",
        "qr_path": str(qr_path.resolve()),
        "entry_id": issued["entry_id"],
        "title": issued["title"],
        "user_code": issued["user_code"],
        "issued_at": datetime.now().astimezone().isoformat(),
    }, ensure_ascii=False), flush=True)

    login_info = poll_login(
        args.host,
        token=qr_token,
        client_id=issued["client_id"],
        user_code=issued["user_code"],
        timeout_s=args.timeout,
        interval_s=args.interval,
    )
    result = apply_and_persist(
        args.host,
        entry_id=issued["entry_id"],
        user_code=issued["user_code"],
        login_info=login_info,
    )
    print(json.dumps({"status": "reauth_applied", "result": result}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
