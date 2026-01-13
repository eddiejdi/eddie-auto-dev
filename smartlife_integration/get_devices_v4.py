#!/usr/bin/env python3
"""
Tuya Cloud - Buscar dispositivos via APIs corretas.
"""
import json
import time
import hmac
import hashlib
import requests

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
BASE_URL = "https://openapi.tuyaus.com"

def calc_sign(client_id, secret, t, access_token="", string_to_hash=""):
    message = client_id
    if access_token:
        message += access_token
    message += t
    message += string_to_hash
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest().upper()

def get_string_to_sign(method, path, body=""):
    content_sha256 = hashlib.sha256(body.encode() if body else b"").hexdigest()
    return f"{method.upper()}\n{content_sha256}\n\n{path}"

def api_get(path, token=None):
    t = str(int(time.time() * 1000))
    string_to_sign = get_string_to_sign("GET", path)
    sign = calc_sign(ACCESS_ID, ACCESS_SECRET, t, access_token=token or "", string_to_hash=string_to_sign)
    
    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        't': t,
        'sign_method': 'HMAC-SHA256',
    }
    if token:
        headers['access_token'] = token
    
    return requests.get(BASE_URL + path, headers=headers).json()

print("=" * 60)
print("   🏠 Tuya Cloud - Buscar Dispositivos v4")
print("=" * 60)
print()

# 1. Token
print("🔑 Obtendo token...")
result = api_get("/v1.0/token?grant_type=1")
if not result.get('success'):
    print(f"❌ Erro token: {result}")
    exit(1)

token = result['result']['access_token']
print(f"✅ Token OK!")
print()

# 2. Listar usuários vinculados (Link App Account)
print("👥 Buscando usuários vinculados ao projeto...")
endpoints_to_try = [
    "/v1.0/iot-03/users",
    "/v1.0/token/users",
    "/v1.0/apps/link-users",
    "/v2.0/apps/link-users",
]

for endpoint in endpoints_to_try:
    print(f"   Tentando: {endpoint}...", end=" ")
    result = api_get(endpoint, token)
    if result.get('success'):
        print(f"✅ OK!")
        users = result.get('result', [])
        print(f"   Usuários: {json.dumps(users, indent=2)[:500]}")
        
        # Buscar dispositivos de cada usuário
        if users:
            for user in users:
                uid = user.get('uid')
                if uid:
                    print(f"\n📱 Buscando dispositivos do usuário {uid}...")
                    devices = api_get(f"/v1.0/users/{uid}/devices", token)
                    if devices.get('success'):
                        dev_list = devices.get('result', [])
                        print(f"   ✅ Encontrados {len(dev_list)} dispositivos!")
                        for d in dev_list:
                            print(f"      - {d.get('name')} ({d.get('id')})")
                    else:
                        print(f"   ❌ {devices.get('msg')}")
        break
    else:
        print(f"❌ {result.get('msg', '?')[:40]}")

print()
print("=" * 60)
