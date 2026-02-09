#!/usr/bin/env python3
"""
Assistente de configuração de credenciais bancárias — Eddie Banking Agent.

Guia interativo para configurar:
  1. Belvo (Open Finance — Santander, Itaú, Nubank)
  2. Mercado Pago (API proprietária)

Armazena credenciais nos vaults do Eddie (Bitwarden, env vars, GPG fallback).

Uso:
  python3 specialized_agents/banking/setup_credentials.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from getpass import getpass
from datetime import datetime

# Diretório de dados
DATA_DIR = Path(__file__).parent.parent.parent / "agent_data" / "banking"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = DATA_DIR / ".env"
STATUS_FILE = DATA_DIR / "setup_status.json"

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║            🏦 Eddie Banking Agent — Setup                    ║
║                                                              ║
║  Configuração de credenciais para integração bancária PF     ║
╚══════════════════════════════════════════════════════════════╝
"""

# ──────────── Helpers ────────────

def colored(text: str, color: str) -> str:
    colors = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "cyan": "\033[96m", "bold": "\033[1m", "reset": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def save_env_var(key: str, value: str):
    """Salva variável no .env e exporta para o processo."""
    os.environ[key] = value
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
    # Atualizar ou adicionar
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o600)


def save_status(provider: str, status: dict):
    """Salva status de configuração."""
    all_status = {}
    if STATUS_FILE.exists():
        all_status = json.loads(STATUS_FILE.read_text())
    all_status[provider] = {**status, "updated_at": datetime.now().isoformat()}
    STATUS_FILE.write_text(json.dumps(all_status, indent=2))


def try_gpg_vault(key: str, value: str) -> bool:
    """Tenta salvar no vault GPG se disponível."""
    vault_dir = Path(__file__).parent.parent.parent / "tools" / "simple_vault" / "secrets"
    if not vault_dir.exists():
        return False
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--yes", "-e", "-r", os.getenv("GPG_KEY_ID", "eddie")],
            input=f"{key}={value}\n".encode(),
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            (vault_dir / f"{key}.gpg").write_bytes(result.stdout)
            return True
    except Exception:
        pass
    return False


# ──────────── Setup Belvo ────────────

def setup_belvo():
    print(colored("\n═══ 1. Belvo (Open Finance Brasil) ═══", "cyan"))
    print("""
O Belvo é o agregador que permite acessar seus dados bancários
de Santander, Itaú e Nubank como Pessoa Física, sem necessidade
de certificados mTLS ou registro como ITP/ITD.

📋 Passo a passo:
""")
    print(colored("  1.", "bold"), "Acesse https://dashboard.belvo.com/signup/")
    print(colored("  2.", "bold"), "Crie uma conta gratuita (sandbox)")
    print(colored("  3.", "bold"), "No Dashboard → API Keys → copie o Secret ID e Secret Password")
    print(colored("  4.", "bold"), "Cole abaixo:\n")

    secret_id = input("  BELVO_SECRET_ID: ").strip()
    if not secret_id:
        print(colored("  ⏭  Pulando configuração Belvo", "yellow"))
        save_status("belvo", {"configured": False, "reason": "skipped"})
        return False

    secret_password = getpass("  BELVO_SECRET_PASSWORD: ").strip()
    if not secret_password:
        print(colored("  ❌ Password vazio, abortando", "red"))
        return False

    env_choice = input(f"\n  Ambiente [{colored('sandbox', 'green')}/production]: ").strip() or "sandbox"

    save_env_var("BELVO_SECRET_ID", secret_id)
    save_env_var("BELVO_SECRET_PASSWORD", secret_password)
    save_env_var("BELVO_ENV", env_choice)

    # Tentar salvar no vault GPG
    try_gpg_vault("BELVO_SECRET_ID", secret_id)
    try_gpg_vault("BELVO_SECRET_PASSWORD", secret_password)

    print(colored(f"\n  ✅ Belvo configurado ({env_choice})", "green"))
    print(f"  📁 Credenciais em: {ENV_FILE}")

    save_status("belvo", {"configured": True, "environment": env_choice})

    print(colored("\n  ℹ  Próximo passo:", "cyan"))
    print("  Após iniciar o agent, use o Belvo Connect Widget para")
    print("  vincular suas contas Santander/Itaú/Nubank.")
    print("  O widget fará o fluxo de consentimento Open Finance.")

    return True


# ──────────── Setup Mercado Pago ────────────

def setup_mercadopago():
    print(colored("\n═══ 2. Mercado Pago ═══", "cyan"))
    print("""
O Mercado Pago usa uma API proprietária. Você precisa criar
um "aplicativo" no portal de desenvolvedores para obter o token.

📋 Passo a passo:
""")
    print(colored("  1.", "bold"), "Acesse https://www.mercadopago.com.br/developers/panel/app")
    print(colored("  2.", "bold"), "Faça login com sua conta Mercado Livre/Mercado Pago")
    print(colored("  3.", "bold"), "Clique em '+ Criar aplicação'")
    print(colored("  4.", "bold"), "Preencha:")
    print("     • Nome: 'Eddie Banking Agent'")
    print("     • Selecione: 'Pagamentos online' → 'Checkout Pro'")
    print("     • Aceite os termos")
    print(colored("  5.", "bold"), "Na aplicação criada → 'Credenciais de produção'")
    print("     • Copie o Access Token (começa com APP_USR-)")
    print(colored("  6.", "bold"), "Cole abaixo:\n")

    access_token = getpass("  BANK_MERCADOPAGO_ACCESS_TOKEN: ").strip()
    if not access_token:
        print(colored("  ⏭  Pulando configuração Mercado Pago", "yellow"))
        save_status("mercadopago", {"configured": False, "reason": "skipped"})
        return False

    save_env_var("BANK_MERCADOPAGO_ACCESS_TOKEN", access_token)
    try_gpg_vault("BANK_MERCADOPAGO_ACCESS_TOKEN", access_token)

    print(colored("\n  ✅ Mercado Pago configurado", "green"))
    print(f"  📁 Token em: {ENV_FILE}")

    # Teste básico
    print("\n  🔍 Testando conexão...")
    try:
        import httpx
        resp = httpx.get(
            "https://api.mercadopago.com/v1/account/bank_report/config",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            print(colored("  ✅ Conexão com Mercado Pago OK!", "green"))
            save_status("mercadopago", {"configured": True, "tested": True})
        elif resp.status_code == 401:
            print(colored("  ⚠️  Token inválido ou expirado. Verifique no portal.", "yellow"))
            save_status("mercadopago", {"configured": True, "tested": False, "error": "401"})
        else:
            print(colored(f"  ⚠️  HTTP {resp.status_code} — verifique manualmente", "yellow"))
            save_status("mercadopago", {"configured": True, "tested": False, "error": str(resp.status_code)})
    except ImportError:
        print("  ℹ  httpx não disponível, teste pulado")
        save_status("mercadopago", {"configured": True, "tested": False})
    except Exception as e:
        print(colored(f"  ⚠️  Erro no teste: {e}", "yellow"))
        save_status("mercadopago", {"configured": True, "tested": False, "error": str(e)})

    return True


# ──────────── Systemd integration ────────────

def show_systemd_hint():
    print(colored("\n═══ Integração com Systemd ═══", "cyan"))
    print(f"""
Para que os serviços systemd (specialized-agents-api, etc) usem as credenciais, 
crie um drop-in de ambiente:

  sudo mkdir -p /etc/systemd/system/specialized-agents-api.service.d
  sudo tee /etc/systemd/system/specialized-agents-api.service.d/banking.conf <<EOF
[Service]
EnvironmentFile={ENV_FILE.absolute()}
EOF
  sudo systemctl daemon-reload
  sudo systemctl restart specialized-agents-api

Ou carregue manualmente no shell:
  source {ENV_FILE.absolute()}
""")


# ──────────── Main ────────────

def main():
    print(BANNER)

    print(colored("Verificando estado atual...\n", "bold"))

    # Verificar configurações existentes
    existing = {}
    if STATUS_FILE.exists():
        existing = json.loads(STATUS_FILE.read_text())

    # Belvo
    belvo_configured = bool(os.getenv("BELVO_SECRET_ID")) or existing.get("belvo", {}).get("configured", False)
    print(f"  Belvo:        {'✅ configurado' if belvo_configured else '❌ não configurado'}")

    # Mercado Pago
    mp_configured = bool(os.getenv("BANK_MERCADOPAGO_ACCESS_TOKEN")) or existing.get("mercadopago", {}).get("configured", False)
    print(f"  Mercado Pago: {'✅ configurado' if mp_configured else '❌ não configurado'}")

    print()

    # Setup
    if not belvo_configured or input(f"  Reconfigurar Belvo? [s/{colored('N', 'bold')}]: ").strip().lower() == 's':
        setup_belvo()
    else:
        print(colored("  ⏭  Belvo já configurado", "green"))

    if not mp_configured or input(f"\n  Reconfigurar Mercado Pago? [s/{colored('N', 'bold')}]: ").strip().lower() == 's':
        setup_mercadopago()
    else:
        print(colored("  ⏭  Mercado Pago já configurado", "green"))

    show_systemd_hint()

    print(colored("\n✅ Setup concluído!", "green"))
    print("""
Próximos passos:
  1. Se configurou Belvo sandbox → vincule bancos pelo widget
  2. Reinicie os serviços: sudo systemctl restart specialized-agents-api
  3. Teste: curl http://localhost:8503/banking/status
  4. No Telegram: /bancos
""")


if __name__ == "__main__":
    main()
