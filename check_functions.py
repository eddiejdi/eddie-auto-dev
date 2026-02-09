#!/usr/bin/env python3
"""Verifica e corrige funções no Open WebUI"""
import requests

email = 'edenilson.teixeira@rpa4all.com'
password = 'Eddie@2026'
base_url = 'http://192.168.15.2:3000'

r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Listar funções
r = requests.get(f'{base_url}/api/v1/functions/', headers=headers)
print('FUNÇÕES INSTALADAS:')
for f in r.json():
    ftype = f.get('type', 'N/A')
    active = '✅' if f.get('is_active') else '❌'
    print(f"  {active} {f.get('id')}: type={ftype}, name={f.get('name')}")

# Verificar se as funções são do tipo correto para aparecer como modelo
print('\n' + '='*50)
print('NOTA: Funções tipo "pipe" aparecem como modelos no dropdown')
print('Funções tipo "filter" modificam mensagens em modelos existentes')
print('='*50)
