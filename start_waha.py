#!/usr/bin/env python3
"""Script para iniciar sessão WAHA"""

import requests

WAHA_URL = "http://localhost:3001"

# Iniciar sessão default
response = requests.post(f"{WAHA_URL}/api/sessions/start", json={"name": "default"})
print(f"Status: {response.status_code}")
print(f"Resposta: {response.text}")
