#!/usr/bin/env python3
"""Login único para evitar rate limit."""
import json
import hashlib
import requests

USERNAME = 'edenilson.adm@gmail.com'
PASSWORD = 'Eddie_88_tp!'

password_hash = hashlib.md5(PASSWORD.encode()).hexdigest()

# Tentar US com smart_life
endpoint = 'https://px1.tuyaus.com'

data = {
    'userName': USERNAME,
    'password': password_hash,
    'countryCode': '55',
    'bizType': 'smart_life',
    'from': 'tuya'
}

print('🔐 Tentando login US/smart_life...')
response = requests.post(f'{endpoint}/homeassistant/auth.do', data=data, timeout=15)
result = response.json()
print(f'📋 Resposta: {json.dumps(result, indent=2)}')

if result.get('access_token'):
    print('✅ LOGIN OK!')
else:
    print(f'❌ Erro: {result.get("errorMsg", result.get("msg", "?"))}')
