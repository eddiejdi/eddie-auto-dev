#!/usr/bin/env python3
"""Testa o shared-assistant com o mesmo prompt do Open WebUI"""

import requests

# Simula exatamente o prompt que o usuário enviou no Open WebUI
prompt = "envie uma mensagem de amor para Fernanda 11986117521 em cópia 11981193899"

response = requests.post(
    'http://192.168.15.2:11434/api/generate',
    json={
        'model': 'shared-assistant',
        'prompt': prompt,
        'stream': False
    },
    timeout=120
)

print("="*60)
print("Modelo: shared-assistant")
print(f"Prompt: {prompt}")
print("-"*60)
print("Resposta:")
print(response.json().get('response', 'Sem resposta'))
