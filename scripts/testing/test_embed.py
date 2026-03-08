#!/usr/bin/env python3
"""Teste de embedding"""
import os
import requests

OLLAMA_URL = os.environ.get('OLLAMA_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

resp = requests.post(
    f"{OLLAMA_URL}/api/embeddings",
    json={'model': 'nomic-embed-text', 'prompt': 'teste'},
    timeout=30
)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    emb = resp.json()['embedding']
    print(f'Embedding: {len(emb)} dimensões')
else:
    print(resp.text)
