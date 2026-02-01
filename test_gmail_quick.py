#!/usr/bin/env python3
"""Teste rápido do Gmail"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json

# Carregar token
with open("/home/homelab/myClaude/gmail_data/token.json") as f:
    token_data = json.load(f)

creds = Credentials(
    token=token_data["token"],
    refresh_token=token_data.get("refresh_token"),
    token_uri=token_data["token_uri"],
    client_id=token_data["client_id"],
    client_secret=token_data["client_secret"],
)

service = build("gmail", "v1", credentials=creds)
results = service.users().messages().list(userId="me", maxResults=10).execute()
messages = results.get("messages", [])

print("=" * 60)
print("📧 SEUS ÚLTIMOS 10 EMAILS:")
print("=" * 60)

for i, msg in enumerate(messages, 1):
    msg_data = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From"],
        )
        .execute()
    )
    headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
    de = headers.get("From", "N/A")
    assunto = headers.get("Subject", "Sem assunto")
    print(f"\n{i}. De: {de[:60]}")
    print(f"   Assunto: {assunto[:70]}")

print("\n" + "=" * 60)
print("✅ Gmail funcionando!")
