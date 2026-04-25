#!/usr/bin/env python3
"""Mirror Smart Life/Home Assistant secrets from Secrets Agent local vault to Authentik.

This script is meant to run on the homelab host. It does not contain secret
values; it reads the already-populated Secrets Agent local vault and stores each
short value in an Authentik OAuth2 provider's client_secret field.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import subprocess
from pathlib import Path


DEFAULT_APP_DIR = Path("/var/lib/eddie/secrets_agent")

SECRET_MAPPINGS = [
    ("shared/home_assistant_url", "password", "secret-homeassistant-url-password"),
    ("shared/home_assistant_url", "url", "secret-homeassistant-url"),
    ("shared/home_assistant_user", "username", "secret-homeassistant-user"),
    ("shared/home_assistant_password", "password", "secret-homeassistant-password"),
    ("shared/smartlife_tuya_account", "username", "secret-smartlife-tuya-username"),
    ("shared/smartlife_tuya_account", "endpoint", "secret-smartlife-tuya-endpoint"),
    ("shared/smartlife_tuya_account", "user_code", "secret-smartlife-tuya-user-code"),
    (
        "shared/smartlife_tuya_account",
        "ha_config_entry_id",
        "secret-smartlife-tuya-ha-entry-id",
    ),
]


class LocalVaultReader:
    def __init__(self, app_dir: Path) -> None:
        self.vault_dir = app_dir / "local_vault"
        passfile = app_dir / "simple_vault_passphrase"
        self.key = hashlib.sha256(passfile.read_text().strip().encode()).digest()

    @staticmethod
    def safe_filename(name: str, field: str) -> str:
        tag = hashlib.sha256(f"{name}:{field}".encode()).hexdigest()[:16]
        return f"{tag}.json"

    def sign(self, data: bytes) -> str:
        return hmac.new(self.key, data, hashlib.sha256).hexdigest()

    def xor_crypt(self, data: bytes) -> bytes:
        stream = hashlib.sha256(self.key + b"stream").digest()
        out = bytearray(len(data))
        for i, _ in enumerate(data):
            ki = i % len(stream)
            if ki == 0 and i > 0:
                stream = hashlib.sha256(self.key + stream).digest()
            out[i] = data[i] ^ stream[ki]
        return bytes(out)

    def get(self, name: str, field: str) -> str:
        path = self.vault_dir / self.safe_filename(name, field)
        envelope = json.loads(path.read_text())
        data = envelope["data"]
        if not hmac.compare_digest(self.sign(data.encode()), envelope["sig"]):
            raise RuntimeError(f"HMAC mismatch for {name}#{field}")
        payload = json.loads(data)
        return self.xor_crypt(base64.b64decode(payload["value"])).decode()


def build_authentik_script(records: list[dict[str, str]]) -> str:
    records_json = json.dumps(records)
    return f"""
import json
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import (
    OAuth2Provider,
    RedirectURI,
    RedirectURIMatchingMode,
)

records = json.loads({records_json!r})
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
    verified = OAuth2Provider.objects.get(pk=provider.pk).client_secret == rec["value"]
    results.append({{
        "client_id": rec["client_id"],
        "created": created,
        "verified": verified,
    }})

print("AUTHENTIK_SECRET_STORE_RESULT=" + json.dumps(results, sort_keys=True))
"""


def collect_records(vault: LocalVaultReader) -> list[dict[str, str]]:
    records = []
    for secret_name, field, client_id in SECRET_MAPPINGS:
        value = vault.get(secret_name, field)
        if len(value) > 255:
            raise ValueError(
                f"{secret_name}#{field} is too long for Authentik client_secret"
            )
        records.append(
            {
                "source_name": secret_name,
                "field": field,
                "client_id": client_id,
                "name": f"Secret Holder - {secret_name}#{field}",
                "value": value,
            }
        )
    return records


def run_authentik_shell(script: str, container: str) -> list[dict[str, object]]:
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "ak", "shell"],
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )
    marker = "AUTHENTIK_SECRET_STORE_RESULT="
    result_line = next(
        (line for line in proc.stdout.splitlines() if line.startswith(marker)),
        None,
    )
    if proc.returncode != 0 or not result_line:
        tail = "\n".join(proc.stdout.splitlines()[-20:])
        raise RuntimeError(
            f"authentik shell failed rc={proc.returncode}, marker={bool(result_line)}\n{tail}"
        )
    return json.loads(result_line[len(marker) :])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR)
    parser.add_argument("--container", default="authentik-server")
    args = parser.parse_args()

    vault = LocalVaultReader(args.app_dir)
    records = collect_records(vault)
    results = run_authentik_shell(build_authentik_script(records), args.container)
    sanitized = [
        {
            "client_id": item["client_id"],
            "created": item["created"],
            "verified": item["verified"],
        }
        for item in results
    ]
    print(
        json.dumps(
            {
                "ok": all(item["verified"] for item in results),
                "stored_count": len(results),
                "records": sanitized,
            },
            indent=2,
        )
    )
    return 0 if all(item["verified"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
