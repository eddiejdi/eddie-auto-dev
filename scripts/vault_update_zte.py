#!/usr/bin/env python3
"""Atualiza credenciais ZTE no local vault do secrets agent.

Uso: python3 vault_update_zte.py <username> <password>
"""
import sys
import os
from pathlib import Path


def main() -> None:
    """Atualiza vault com credenciais ZTE fornecidas."""
    if len(sys.argv) != 3:
        print("Uso: vault_update_zte.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    os.environ.setdefault("SECRETS_AGENT_DATA", "/var/lib/eddie/secrets_agent")

    # Ajustar path para importar o módulo
    repo_root = Path("/home/homelab/eddie-auto-dev")
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from tools.secrets_agent.secrets_agent import local_vault  # noqa: PLC0415

    ok_user = local_vault.store("network/zte_gpon_modem", username, field="username")
    ok_pass = local_vault.store("network/zte_gpon_modem", password, field="password")

    u = local_vault.get("network/zte_gpon_modem", "username")
    p = local_vault.get("network/zte_gpon_modem", "password")
    print(f"vault username: {u!r} (ok={ok_user})")
    print(f"vault password ok: {bool(p)} (ok={ok_pass})")


if __name__ == "__main__":
    main()
