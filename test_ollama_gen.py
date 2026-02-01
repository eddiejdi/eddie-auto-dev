#!/usr/bin/env python3
"""Teste de geração Ollama"""

import requests

resp = requests.post(
    "http://192.168.15.2:11434/api/generate",
    json={"model": "eddie-assistant", "prompt": "Ola, tudo bem?", "stream": False},
    timeout=60,
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Resposta: {data.get('response', 'Sem resposta')[:200]}")
else:
    print(f"Erro: {resp.text}")
