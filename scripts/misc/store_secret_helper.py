#!/usr/bin/env python3
"""Auxiliar para armazenar um secret no Secrets Agent.
Lê credenciais exclusivamente de variáveis de ambiente:
  SECRET_NAME  — nome do secret
  SECRET_VALUE — valor a armazenar
  SECRET_FIELD — campo (default: password)
  SECRET_NOTES — notas opcionais
  SA_KEY       — X-API-KEY do Secrets Agent
  SA_URL       — URL do Secrets Agent (default: http://192.168.15.2:8088)
"""
import os, json, sys, urllib.request

url  = os.environ.get("SA_URL", "http://192.168.15.2:8088") + "/secrets"
body = json.dumps({
    "name":  os.environ["SECRET_NAME"],
    "value": os.environ["SECRET_VALUE"],
    "field": os.environ.get("SECRET_FIELD", "password"),
    "notes": os.environ.get("SECRET_NOTES", ""),
}).encode()

req = urllib.request.Request(url, data=body, method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("X-API-KEY", os.environ["SA_KEY"])

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(f"OK HTTP {r.status}: {r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"ERRO HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
    sys.exit(1)
