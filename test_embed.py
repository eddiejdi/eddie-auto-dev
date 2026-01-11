#!/usr/bin/env python3
"""Teste de embedding"""
import requests

resp = requests.post(
    'http://192.168.15.2:11434/api/embeddings',
    json={'model': 'nomic-embed-text', 'prompt': 'teste'},
    timeout=30
)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    emb = resp.json()['embedding']
    print(f'Embedding: {len(emb)} dimensões')
else:
    print(resp.text)
