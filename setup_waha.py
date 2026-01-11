#!/usr/bin/env python3
"""Script para configurar sessão WAHA"""
import requests
import json

WAHA_URL = "http://localhost:3001"
API_KEY = "eddie123"

headers = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Criar sessão
print("Criando sessão WhatsApp...")
response = requests.post(
    f"{WAHA_URL}/api/sessions/start",
    headers=headers,
    json={"name": "eddie"}
)
print(f"Status: {response.status_code}")
print(f"Resposta: {response.text}")

# Verificar sessões
print("\nSessões ativas:")
response = requests.get(f"{WAHA_URL}/api/sessions", headers=headers)
print(response.json())
