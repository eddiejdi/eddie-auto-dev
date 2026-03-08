#!/usr/bin/env python3
"""Teste simples de criação de modelo"""

import os
import requests
import json

# Teste simples
modelfile = '''FROM qwen2.5-coder:7b
SYSTEM """Teste simples"""
'''

OLLAMA_URL = os.environ.get('OLLAMA_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

r = requests.post(
    f"{OLLAMA_URL}/api/create",
    json={'name': 'test-simple', 'modelfile': modelfile, 'stream': False}
)
print('Status:', r.status_code)
print('Response:', r.text[:500])
