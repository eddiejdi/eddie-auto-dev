#!/usr/bin/env python3
"""Login testando EU."""
import json
import hashlib
import os
import requests

USERNAME = 'edenilson.teixeira@rpa4all.com'
PASSWORD = os.environ["TUYA_PASSWORD"]

password_hash = hashlib.md5(PASSWORD.encode()).hexdigest()

# Tentar EU com smart_life
endpoint = 'https://px1.tuyaeu.com'

data = {
    'userName': USERNAME,
    'password': password_hash,
    'countryCode': '55',
    'bizType': 'smart_life',
    'from': 'tuya'
}

print('🔐 Tentando login EU/smart_life...')
response = requests.post(f'{endpoint}/homeassistant/auth.do', data=data, timeout=15)
result = response.json()
print(f'📋 Resposta: {json.dumps(result, indent=2)}')

if result.get('access_token'):
    print('✅ LOGIN OK!')
else:
    print(f'❌ Erro: {result.get("errorMsg", result.get("msg", "?"))}')
