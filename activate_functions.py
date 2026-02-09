#!/usr/bin/env python3
"""Ativa todas as funções no Open WebUI"""
import requests

email = 'edenilson.teixeira@rpa4all.com'
password = 'Eddie@2026'
base_url = 'http://192.168.15.2:3000'

r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Verificar status atual e ativar se necessário
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
for f in r.json():
    fid = f.get('id')
    is_active = f.get('is_active', False)
    
    if not is_active:
        # Toggle para ativar
        r2 = requests.post(f'{base_url}/api/v1/functions/id/{fid}/toggle', headers=headers)
        print(f'Ativando {fid}: {r2.status_code}')
    else:
        print(f'{fid}: já ativo')

# Verificar status final
print('\nStatus final:')
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
for f in r.json():
    status = '✅' if f.get('is_active') else '❌'
    print(f"  {status} {f.get('id')}: {f.get('name')}")
