#!/usr/bin/env python3
"""Teste rápido Gmail"""

import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

with open("/home/homelab/myClaude/gmail_data/token.json", encoding="utf-8-sig") as f:
    t = json.load(f)

creds = Credentials(
    token=t["token"],
    refresh_token=t.get("refresh_token"),
    token_uri=t["token_uri"],
    client_id=t["client_id"],
    client_secret=t["client_secret"],
)

svc = build("gmail", "v1", credentials=creds)
res = svc.users().messages().list(userId="me", maxResults=3).execute()
print("OK! Emails:", len(res.get("messages", [])))
for m in res.get("messages", []):
    print(f"  ID: {m['id']}")
