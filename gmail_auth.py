#!/usr/bin/env python3
"""Autenticação Gmail com Desktop App credentials"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDS_FILE = "/home/homelab/myClaude/credentials.json"
TOKEN_FILE = "/home/homelab/myClaude/gmail_data/token.json"


def main():
    os.makedirs("/home/homelab/myClaude/gmail_data", exist_ok=True)

    print("=" * 60)
    print("🔐 AUTENTICAÇÃO GMAIL")
    print("=" * 60)

    # Verificar credenciais
    if not os.path.exists(CREDS_FILE):
        print(f"❌ Arquivo {CREDS_FILE} não encontrado!")
        return

    print(f"✅ Credenciais: {CREDS_FILE}")

    # Iniciar fluxo OAuth
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)

    print("\n🌐 Iniciando servidor local na porta 8080...")
    print("   Acesse a URL abaixo no navegador:\n")

    # Não abre navegador automaticamente (WSL não consegue)
    creds = flow.run_local_server(port=8080, open_browser=False)

    # Salvar token
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ GMAIL CONECTADO COM SUCESSO!")
    print("=" * 60)
    print(f"📁 Token salvo em: {TOKEN_FILE}")
    print("\nAgora você pode usar os comandos:")
    print("  /gmail listar")
    print("  /gmail treinar")
    print("  /gmail buscar <termo>")


if __name__ == "__main__":
    main()
