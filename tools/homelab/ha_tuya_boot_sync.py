#!/usr/bin/env python3
"""Boot sync do Home Assistant + Tuya.

Roda uma vez após o boot (systemd `ha-tuya-boot-sync.service`):

1. Garante que o container `homeassistant` esteja em execução (`docker start`
   se estiver parado) — cobre o gap 2026-08-10 em que o container saiu antes
   do reboot e a policy `unless-stopped` não o reiniciou.
2. Aguarda o HA responder na API local (healthcheck/HTTP 200).
3. Recarrega a config entry do domínio `tuya` (reload é idempotente e não
   grava storage — não conflita com o self-heal que roda no timer).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

CONTAINER = "homeassistant"
HA_URL = "http://127.0.0.1:8123"
WAIT_API_S = 300
POLL_S = 10
EXEC_TIMEOUT_S = 60


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def container_running() -> bool:
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def ensure_container() -> bool:
    if container_running():
        log("container %s já em execução" % CONTAINER)
        return True
    log("container %s parado — emitindo docker start" % CONTAINER)
    proc = subprocess.run(
        ["docker", "start", CONTAINER],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        log("docker start falhou: %s" % (proc.stderr or proc.stdout).strip()[:200])
        return False
    return True


def wait_ha_api(timeout_s: int = WAIT_API_S) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{HA_URL}/", timeout=10) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception:
            pass
        time.sleep(POLL_S)
    return False


def docker_exec(script: str, timeout: int = EXEC_TIMEOUT_S) -> str:
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return proc.stdout.strip()


def get_jwt() -> str:
    return docker_exec(
        "import json,jwt,time;"
        "a=json.load(open('/config/.storage/auth'));"
        "tok=next(t for t in a['data']['refresh_tokens'] "
        "if t.get('token_type')=='long_lived_access_token');"
        "print(jwt.encode({'iss':tok['id'],'iat':int(time.time()),"
        "'exp':int(time.time())+300},tok['jwt_key'],algorithm='HS256'))"
    )


def reload_tuya_entry() -> tuple[int, bool]:
    entry_id = docker_exec(
        "import json;d=json.load(open('/config/.storage/core.config_entries'));"
        "e=[x for x in d['data']['entries'] if x['domain']=='tuya'];"
        "print(e[0]['entry_id'] if e else '')"
    )
    if not entry_id:
        return 0, False
    req = urllib.request.Request(
        f"{HA_URL}/api/config/config_entries/entry/{entry_id}/reload",
        method="POST",
        headers={
            "Authorization": f"Bearer {get_jwt()}",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, 200 <= resp.status < 300


def main() -> int:
    exit_code = 0
    if not ensure_container():
        return 2
    if not wait_ha_api():
        log("timo esgotado aguardando a API do HA responder")
        return 3
    try:
        status, ok = reload_tuya_entry()
        log("reload entry tuya: http=%s ok=%s" % (status, ok))
        if not ok:
            exit_code = 4
    except Exception as exc:  # noqa: BLE001
        log("falha ao recarregar entry tuya: %s" % exc)
        exit_code = 5
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())