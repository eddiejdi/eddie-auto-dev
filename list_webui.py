#!/usr/bin/env python3
"""Lista funções e modelos do Open WebUI"""
import requests

email = 'edenilson.teixeira@rpa4all.com'
password = 'Eddie@2026'
import os

base_url = os.environ.get('HOMELAB_URL', 'http://localhost:3000')

# Login
r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Listar funções
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
print('FUNÇÕES INSTALADAS:')
for f in r.json():
    print(f"  - {f.get('id')}: {f.get('name')} (ativo: {f.get('is_active', False)})")

# Listar modelos
r = requests.get(f'{base_url}/api/models/', headers=headers)
print()
print('MODELOS DISPONÍVEIS:')
if r.status_code == 200:
    data = r.json()
    models = data.get('models', data) if isinstance(data, dict) else data
    for m in models[:10]:
        name = m.get('name') or m.get('id', 'N/A')
        print(f"  - {name}")
