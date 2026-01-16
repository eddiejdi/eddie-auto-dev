#!/usr/bin/env python3
"""Ativa todas as funções no Open WebUI"""
import requests

email = 'edenilson.adm@gmail.com'
password = 'Eddie@2026'
base_url = 'http://192.168.15.2:3000'

r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Ativar agent_coordinator
r = requests.post(f'{base_url}/api/v1/functions/id/agent_coordinator/toggle', headers=headers)
print(f'Toggle agent_coordinator: {r.status_code}')

# Verificar status
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
print('\nStatus das funções:')
for f in r.json():
    status = '✅' if f.get('is_active') else '❌'
    print(f"  {status} {f.get('id')}: {f.get('name')}")
