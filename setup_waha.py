#!/usr/bin/env python3
"""Script para configurar sessão WAHA"""
import requests
import json

import os

WAHA_URL = os.environ.get("WAHA_URL", "http://localhost:3001")
try:
    from tools.vault.secret_store import get_field
    API_KEY = get_field("eddie/waha_api_key", "password")
except Exception:
    API_KEY = "757fae2686eb44479b9a34f1b62dbaf3"  # Fallback hardcoded

headers = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Criar sessão
print("Criando sessão WhatsApp...")
response = requests.post(
    f"{WAHA_URL}/api/sessions/start",
    headers=headers,
    json={"name": "default"}
)
print(f"Status: {response.status_code}")
print(f"Resposta: {response.text}")

# Verificar sessões
print("\nSessões ativas:")
response = requests.get(f"{WAHA_URL}/api/sessions", headers=headers)
print(response.json())
