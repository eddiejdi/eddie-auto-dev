#!/usr/bin/env python3
"""Testa disponibilidade das APIs SmartLife."""
import requests

print('🔍 Testando APIs SmartLife...')
print()

apis = {
    'eu': 'https://px1.tuyaeu.com',
    'us': 'https://px1.tuyaus.com',
    'cn': 'https://px1.tuyacn.com'
}

for region, url in apis.items():
    try:
        r = requests.get(url, timeout=5)
        print(f'  ✅ {region}: {url} - Status: {r.status_code}')
    except Exception as e:
        print(f'  ❌ {region}: {url} - Erro: {e}')

print()
print('Se alguma API está acessível, você pode usar o login SmartLife!')
print('Execute: python smartlife_login.py')
