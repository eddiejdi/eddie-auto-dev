#!/usr/bin/env python3
"""Testa o eddie-assistant sem restrições"""

import requests

response = requests.post(
    'http://192.168.15.2:11434/api/generate',
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
