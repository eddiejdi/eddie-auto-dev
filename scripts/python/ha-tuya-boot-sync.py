#!/usr/bin/env python3
"""
ha-tuya-boot-sync.py — Reload do Tuya/SmartLife no boot do homelab.

Aguarda o Home Assistant ficar healthy, gera um JWT de acesso a partir do
long-lived token armazenado em /config/.storage/auth e dispara o reload da
integração Tuya para sincronizar dispositivos do SmartLife.
"""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

HA_URL = "http://localhost:8123"
AUTH_STORE = "/config/.storage/auth"
MAX_WAIT = 300   # segundos esperando HA subir
POLL_INTERVAL = 5


def get_tuya_entry_id() -> str:
    """Descobre dinamicamente o entry_id da integração Tuya no HA."""
    result = subprocess.run(
        ["docker", "exec", "homeassistant", "python3", "-c",
         "import json;"
         "d=json.load(open('/config/.storage/core.config_entries'));"
         "e=[x for x in d['data']['entries'] if x['domain']=='tuya'];"
         "print(e[0]['entry_id'] if e else '')"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    entry_id = result.stdout.strip()
    if not entry_id:
        raise RuntimeError("entry_id da integração Tuya não encontrado")
    return entry_id


def get_jwt_token() -> str:
    """Lê o jwt_key do long-lived token e gera um JWT válido por 1 ano."""
    result = subprocess.run(
        ["docker", "exec", "homeassistant", "python3", "-c", f"""
import json, time, jwt
with open('{AUTH_STORE}') as f:
    d = json.load(f)
for t in d['data']['refresh_tokens']:
    if t.get('token_type') == 'long_lived_access_token':
        now = int(time.time())
        payload = {{'iss': t['id'], 'iat': now, 'exp': now + 3600 * 24 * 365}}
        print(jwt.encode(payload, t['jwt_key'], algorithm='HS256'))
        break
"""],
        capture_output=True, text=True, timeout=30
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError(f"Falha ao gerar token: {result.stderr}")
    return token


def wait_for_ha(token: str) -> bool:
    """Aguarda a API do HA responder OK."""
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{HA_URL}/api/",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False


def reload_tuya(token: str, entry_id: str) -> bool:
    """Dispara reload da integração Tuya."""
    url = f"{HA_URL}/api/config/config_entries/entry/{entry_id}/reload"
    req = urllib.request.Request(url, data=b"", method="POST",
                                  headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
            return body.get("require_restart") is not None
    except urllib.error.HTTPError as e:
        print(f"Erro HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return False


def main():
    print("[ha-tuya-boot-sync] Gerando token JWT...")
    token = get_jwt_token()

    print("[ha-tuya-boot-sync] Aguardando Home Assistant...")
    if not wait_for_ha(token):
        print("[ha-tuya-boot-sync] Timeout — HA não respondeu em tempo.", file=sys.stderr)
        sys.exit(1)

    print("[ha-tuya-boot-sync] Descobrindo entry_id da integração Tuya...")
    entry_id = get_tuya_entry_id()

    print("[ha-tuya-boot-sync] Recarregando integração Tuya/SmartLife...")
    if reload_tuya(token, entry_id):
        print("[ha-tuya-boot-sync] Sync Tuya concluído.")
    else:
        print("[ha-tuya-boot-sync] Falha no reload Tuya.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
