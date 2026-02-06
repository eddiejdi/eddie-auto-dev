#!/usr/bin/env python3
"""Testa o eddie-assistant sem restrições"""

import os
import requests

OLLAMA_URL = os.environ.get('OLLAMA_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

response = requests.post(
    f"{OLLAMA_URL}/api/generate",
    json={
        'model': 'eddie-assistant',
        'prompt': 'Escreva uma mensagem de amor para Fernanda Baldi',
        'stream': False
    },
    timeout=120
)

print("="*60)
print("Modelo: eddie-assistant (sem restrições)")
print("Prompt: Escreva uma mensagem de amor para Fernanda Baldi")
print("-"*60)
print("Resposta:")
print(response.json().get('response', 'Sem resposta'))
