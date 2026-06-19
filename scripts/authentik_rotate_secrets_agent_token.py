#!/usr/bin/env python3
"""Cria (ou recria) um token Authentik permanente para o secrets_agent.

Uso:
  AUTHENTIK_URL=https://auth.rpa4all.com \
  AUTHENTIK_ADMIN_TOKEN=ak-... \
  python3 scripts/authentik_rotate_secrets_agent_token.py

O script:
1. Deleta o token antigo "secrets-agent-api" (se existir)
2. Cria novo token com expiring=False para o superuser akadmin
3. Imprime o UPDATE_CMD a executar com sudo para atualizar o override.conf
4. (Opcional) Aplica o override diretamente se --apply for passado

Nunca loga o valor do token — só imprime o comando de update.
"""
from __future__ import annotations

import argparse
import os
import sys
import requests

IDENTIFIER = "secrets-agent-api"
OVERRIDE_PATH = "/etc/systemd/system/secrets_agent.service.d/override.conf"

requests.packages.urllib3.disable_warnings()  # noqa: E501 — self-signed cert homelab


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}


def get_superuser_pk(base: str, token: str) -> int:
    resp = requests.get(f"{base}/api/v3/core/users/?is_superuser=true&format=json",
                        headers=_headers(token), timeout=10, verify=False)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        sys.exit("Nenhum superuser encontrado no Authentik.")
    return results[0]["pk"]


def delete_old_token(base: str, token: str) -> None:
    resp = requests.get(f"{base}/api/v3/core/tokens/?identifier={IDENTIFIER}&format=json",
                        headers=_headers(token), timeout=10, verify=False)
    resp.raise_for_status()
    for t in resp.json().get("results", []):
        pk = t["pk"]
        del_resp = requests.delete(f"{base}/api/v3/core/tokens/{pk}/",
                                   headers=_headers(token), timeout=10, verify=False)
        if del_resp.status_code in (204, 200):
            print(f"Token antigo deletado: pk={pk}")
        else:
            print(f"Aviso: delete pk={pk} retornou {del_resp.status_code}", file=sys.stderr)


def create_token(base: str, token: str, user_pk: int) -> str:
    payload = {
        "identifier": IDENTIFIER,
        "expiring": False,
        "user": user_pk,
        "description": "Token permanente para secrets_agent (criado por authentik_rotate_secrets_agent_token.py)",
    }
    resp = requests.post(f"{base}/api/v3/core/tokens/", json=payload,
                         headers=_headers(token), timeout=10, verify=False)
    if resp.status_code not in (200, 201):
        sys.exit(f"Criação do token falhou ({resp.status_code}): {resp.text}")
    # Authentik ≥2023.8 não retorna key no POST — usa /view_key/
    key = resp.json().get("key")
    if not key:
        view_resp = requests.get(f"{base}/api/v3/core/tokens/{IDENTIFIER}/view_key/",
                                 headers=_headers(token), timeout=10, verify=False)
        view_resp.raise_for_status()
        key = view_resp.json().get("key")
    if not key:
        sys.exit(f"Não foi possível obter o valor do token: {resp.text}")
    return key


def read_override(path: str) -> list[str]:
    try:
        with open(path) as f:
            return f.readlines()
    except FileNotFoundError:
        return ["[Service]\n"]


def apply_override(path: str, new_token: str) -> None:
    lines = read_override(path)
    new_lines = [l for l in lines if "AUTHENTIK_TOKEN" not in l]
    new_lines.append(f'Environment="AUTHENTIK_TOKEN={new_token}"\n')
    with open(path, "w") as f:
        f.writelines(new_lines)
    print(f"override.conf atualizado: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Aplica o token no override.conf (requer root)")
    ap.add_argument("--reload", action="store_true", help="Executa systemctl daemon-reload + restart secrets_agent")
    args = ap.parse_args()

    base = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
    admin_token = os.environ.get("AUTHENTIK_ADMIN_TOKEN", "").strip()
    if not admin_token:
        sys.exit("AUTHENTIK_ADMIN_TOKEN não definido.")

    print(f"Conectando a {base}...")
    user_pk = get_superuser_pk(base, admin_token)
    print(f"Superuser pk={user_pk}")

    delete_old_token(base, admin_token)
    new_key = create_token(base, admin_token, user_pk)
    print("Novo token criado com expiring=False.")

    if args.apply:
        apply_override(OVERRIDE_PATH, new_key)
        if args.reload:
            import subprocess
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "restart", "secrets_agent"], check=True)
            print("secrets_agent reiniciado.")
    else:
        print("\nPara aplicar, execute como root:")
        print(f"  AUTHENTIK_ADMIN_TOKEN=<token> python3 {__file__} --apply --reload")


if __name__ == "__main__":
    main()
