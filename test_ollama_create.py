#!/usr/bin/env python3
"""Teste simples de criação de modelo"""

import requests
import json

# Teste simples
modelfile = '''FROM qwen2.5-coder:7b
SYSTEM """Teste simples"""
'''

r = requests.post(
    'http://192.168.15.2:11434/api/create',
    json={'name': 'test-simple', 'modelfile': modelfile, 'stream': False}
)
print('Status:', r.status_code)
print('Response:', r.text[:500])
