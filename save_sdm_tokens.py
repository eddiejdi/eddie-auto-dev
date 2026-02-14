#!/usr/bin/env python3
"""Troca um código OAuth por access/refresh token SDM e salva localmente e no Secrets Agent."""
import json
import os
import sys
import urllib.parse
import urllib.request
import subprocess

CREDS_FILE = "credentials_google.json"
TOKEN_URL = "https://oauth2.googleapis.com/token"

def load_client():
    with open(CREDS_FILE) as f:
        c = json.load(f)
        inst = c.get("installed", c.get("web", {}))
    return inst.get("client_id"), inst.get("client_secret"), inst.get("project_id")

def exchange_code(code, client_id, client_secret, redirect_uri="http://localhost:8085"):
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def save_env(tokens, project_id):
    # update .env preserving other lines
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [l for l in f.readlines() if not l.startswith("GOOGLE_HOME_TOKEN=") and not l.startswith("GOOGLE_HOME_REFRESH_TOKEN=") and not l.startswith("GOOGLE_SDM_PROJECT_ID=")]
    lines.append(f"GOOGLE_HOME_TOKEN={tokens.get('access_token')}\n")
    if tokens.get('refresh_token'):
        lines.append(f"GOOGLE_HOME_REFRESH_TOKEN={tokens.get('refresh_token')}\n")
    # project id in format projects/NNN or plain number
    pid = project_id
    if pid and not pid.startswith("projects/"):
        pid = f"projects/{pid}"
    lines.append(f"GOOGLE_SDM_PROJECT_ID={pid}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    print("Saved tokens to .env")

def save_json(tokens, project_id):
    payload = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type"),
        "project_id": project_id,
    }
    with open("google_home_credentials.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("Saved google_home_credentials.json")

def store_secrets_agent(tokens):
    try:
        payload = json.dumps({
            "name": "eddie-google-home-token",
            "value": tokens.get("access_token"),
            "metadata": {"type": "sdm_access_token"}
        })
        cmd = [
            "ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
            f"curl -sf -X POST http://localhost:8088/secrets -H 'Content-Type: application/json' -H 'X-API-Key: eddie-secrets-2026' -d '{payload}'"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            print("Saved access token to Secrets Agent")
        else:
            print("Secrets Agent store failed:", r.stderr.strip()[:200])
    except Exception as e:
        print("Secrets Agent error:", e)

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 save_sdm_tokens.py <AUTH_CODE>")
        sys.exit(1)
    code = sys.argv[1]
    client_id, client_secret, project_id = load_client()
    print("Exchanging code for tokens...")
    try:
        tokens = exchange_code(code, client_id, client_secret)
    except Exception as e:
        print("Error exchanging code:", e)
        sys.exit(1)
    if "access_token" not in tokens:
        print("Exchange failed:", tokens)
        sys.exit(1)
    print("Tokens obtained. Saving...")
    save_env(tokens, project_id)
    save_json(tokens, project_id)
    store_secrets_agent(tokens)
    print("Done.")

if __name__ == '__main__':
    main()
