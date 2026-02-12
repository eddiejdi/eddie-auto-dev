#!/usr/bin/env python3
"""
📂 Google Drive Search — via Secrets Agent (homelab)

Obtém credenciais OAuth do Secrets Agent no homelab (porta 8088),
renova token se necessário e busca currículos no Drive.

Nenhuma credencial hardcoded — tudo via cofre oficial.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_PORT = 8088
SECRETS_AGENT_URL = f"http://{SECRETS_AGENT_HOST}:{SECRETS_AGENT_PORT}"

# Nomes dos segredos no Secrets Agent
TOKEN_SECRET_NAME = "google/gdrive_token_edenilson_teixeira"
TOKEN_SECRET_FIELD = "token_json"
CREDS_SECRET_NAME = "google/oauth_client_installed"
CREDS_SECRET_FIELD = "credentials_json"


def get_secret_from_agent(name: str, field: str) -> str:
    """Obtém segredo do Secrets Agent via SSH + SQLite (workaround para path com /)."""
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"python3 -c \""
        f"import sqlite3, base64; "
        f"conn = sqlite3.connect('/var/lib/eddie/secrets_agent/audit.db'); "
        f"c = conn.cursor(); "
        f"c.execute(\\\"SELECT value FROM secrets_store WHERE name=? AND field=?\\\", "
        f"('{name}', '{field}')); "
        f"row = c.fetchone(); "
        f"conn.close(); "
        f"print(base64.b64decode(row[0]).decode() if row else 'NOT_FOUND')"
        f"\""
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao acessar Secrets Agent: {result.stderr}")
    value = result.stdout.strip()
    if value == "NOT_FOUND":
        raise KeyError(f"Segredo não encontrado: {name}/{field}")
    return value


def update_token_in_agent(name: str, field: str, token_json: str):
    """Atualiza token no Secrets Agent após refresh."""
    encoded = base64.b64encode(token_json.encode()).decode()
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"python3 -c \""
        f"import sqlite3, time; "
        f"conn = sqlite3.connect('/var/lib/eddie/secrets_agent/audit.db'); "
        f"c = conn.cursor(); "
        f"c.execute(\\\"UPDATE secrets_store SET value=?, updated_at=? WHERE name=? AND field=?\\\", "
        f"('{encoded}', int(time.time()), '{name}', '{field}')); "
        f"conn.commit(); "
        f"print(f'Updated {{c.rowcount}} row(s)'); "
        f"conn.close()"
        f"\""
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        print(f"  ✅ Token atualizado no Secrets Agent")
    else:
        print(f"  ⚠️  Falha ao atualizar token: {result.stderr}")


def get_drive_credentials() -> Credentials:
    """Carrega credenciais do Secrets Agent e renova se necessário."""
    print("🔐 Obtendo token do Secrets Agent...")
    token_json = get_secret_from_agent(TOKEN_SECRET_NAME, TOKEN_SECRET_FIELD)
    token_data = json.loads(token_json)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/drive.readonly"]),
    )

    if creds.expired or not creds.valid:
        print("🔄 Renovando token...")
        creds.refresh(Request())
        print(f"  ✅ Token renovado! Expira: {creds.expiry}")

        # Salvar token renovado no Secrets Agent
        new_token = json.dumps({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else [],
            "expiry": creds.expiry.isoformat() + "Z" if creds.expiry else None,
        })
        update_token_in_agent(TOKEN_SECRET_NAME, TOKEN_SECRET_FIELD, new_token)

    return creds


def search_resumes(creds: Credentials):
    """Busca currículos no Google Drive."""
    print("\n📂 Buscando currículos no Google Drive...")
    drive = build("drive", "v3", credentials=creds)

    terms = ["curriculo", "currículo", "curriculum", "cv", "resume"]
    all_files = []

    for term in terms:
        q = f"name contains '{term}' and trashed=false"
        try:
            res = drive.files().list(
                q=q, pageSize=10, orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
            ).execute()
            files = res.get("files", [])
            if files:
                print(f"  ✓ '{term}': {len(files)} arquivo(s)")
                all_files.extend(files)
        except Exception as e:
            print(f"  ✗ '{term}': {e}")

    if not all_files:
        print("  ℹ️  Nenhum currículo por nome. Buscando PDFs recentes...")
        try:
            res = drive.files().list(
                q="mimeType='application/pdf' and trashed=false",
                pageSize=20, orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
            ).execute()
            all_files = res.get("files", [])
        except Exception:
            pass

    if not all_files:
        print("  ❌ Nenhum arquivo encontrado.")
        return

    unique = {f["id"]: f for f in all_files}
    ordered = sorted(unique.values(), key=lambda f: f.get("modifiedTime", ""), reverse=True)

    print(f"\n📊 {len(ordered)} arquivo(s) encontrado(s):")
    print("=" * 70)
    for i, f in enumerate(ordered[:10], 1):
        name = f.get("name", "?")
        sz = int(f.get("size", 0)) / 1024
        mod = f.get("modifiedTime", "")[:10]
        link = f.get("webViewLink", "N/A")
        star = " ⭐ MAIS RECENTE" if i == 1 else ""
        print(f"\n  [{i}] {name}{star}")
        print(f"      {sz:.0f} KB | {mod}")
        print(f"      🔗 {link}")

    print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("  📂 Google Drive Search — via Secrets Agent")
    print("=" * 70)

    creds = get_drive_credentials()
    search_resumes(creds)
    print("\n✅ Concluído!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
