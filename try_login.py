#!/usr/bin/env python3
"""Tenta login no Open WebUI com diferentes emails"""
import requests
import sys

url = 'http://192.168.15.2:3000'
senha = sys.argv[1] if len(sys.argv) > 1 else '123'

emails = [
    'admin@localhost', 
    'eddie@localhost', 
    'admin@admin.com', 
    'eddie@eddie.com',
    'user@localhost',
    'admin@example.com',
    'eddie@example.com'
]

print(f"Tentando login com senha: {senha}")
print("-" * 40)

for email in emails:
    try:
        r = requests.post(
            f'{url}/api/v1/auths/signin', 
            json={'email': email, 'password': senha}, 
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            print(f"✅ SUCCESS: {email}")
            print(f"   Token: {data.get('token', 'N/A')[:50]}...")
            with open('/tmp/webui_token.txt', 'w') as f:
                f.write(data.get('token', ''))
            sys.exit(0)
        else:
            print(f"❌ {email}: {r.status_code}")
    except Exception as e:
        print(f"❌ {email}: {e}")

print("\nNenhum email funcionou. Qual é o email do Open WebUI?")
