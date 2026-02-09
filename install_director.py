#!/usr/bin/env python3
"""Instala a função Diretor no Open WebUI"""
import requests
import sys

email = 'edenilson.teixeira@rpa4all.com'
password = 'Eddie@2026'
base_url = 'http://192.168.15.2:3000'

# Login
r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
if r.status_code != 200:
    print(f'Erro login: {r.status_code}')
    sys.exit(1)
    
token = r.json().get('token')
print('Login OK')

headers = {'Authorization': f'Bearer {token}'}

# Ler função
with open('openwebui_director_function.py', 'r') as f:
    function_code = f.read()

print(f'Função: {len(function_code)} bytes')

# Verificar existente
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
existing = r.json() if r.status_code == 200 else []
function_id = 'director_eddie'
exists = any(f.get('id') == function_id for f in existing)

# Dados
function_data = {
    'id': function_id,
    'name': 'Diretor Eddie',
    'content': function_code,
    'meta': {'description': 'Diretor principal Eddie Auto-Dev'}
}

if exists:
    print('Atualizando...')
    r = requests.post(f'{base_url}/api/v1/functions/id/{function_id}/update', headers=headers, json=function_data)
else:
    print('Criando...')
    r = requests.post(f'{base_url}/api/v1/functions/create', headers=headers, json=function_data)

if r.status_code in [200, 201]:
    print('Instalado!')
    r = requests.post(f'{base_url}/api/v1/functions/id/{function_id}/toggle', headers=headers)
    print('Ativado!' if r.status_code == 200 else 'Erro ativar')
else:
    print(f'Erro: {r.status_code}')
