#!/usr/bin/env python3
"""
Testa todos os endpoints Tuya disponíveis.
"""
import json
import time
import hmac
import hashlib
import requests

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"

ENDPOINTS = {
    "us-east": "https://openapi.tuyaus.com",
    "us-west": "https://openapi-ueaz.tuyaus.com",
    "eu-central": "https://openapi.tuyaeu.com",
    "eu-west": "https://openapi-weaz.tuyaeu.com",
    "china": "https://openapi.tuyacn.com",
    "india": "https://openapi.tuyain.com",
}

def calc_sign(client_id, secret, t, string_to_hash=""):
    message = client_id + t + string_to_hash
    sign = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    return sign

def get_string_to_sign(method, path):
    content_sha256 = hashlib.sha256(b"").hexdigest()
    return method.upper() + "\n" + content_sha256 + "\n" + "\n" + path

def test_endpoint(name, base_url):
    """Testa um endpoint."""
    path = "/v1.0/token?grant_type=1"
    t = str(int(time.time() * 1000))
    string_to_sign = get_string_to_sign("GET", path)
    sign = calc_sign(ACCESS_ID, ACCESS_SECRET, t, string_to_sign)
    
    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        't': t,
        'sign_method': 'HMAC-SHA256',
    }
    
    try:
        response = requests.get(base_url + path, headers=headers, timeout=10)
        result = response.json()
        
        if result.get('success'):
            token = result['result']['access_token']
            uid = result['result']['uid']
            
            # Tentar buscar dispositivos
            t2 = str(int(time.time() * 1000))
            path2 = f"/v1.0/users/{uid}/devices"
            string_to_sign2 = get_string_to_sign("GET", path2)
            sign2 = calc_sign(ACCESS_ID, ACCESS_SECRET, t2, token + string_to_sign2)
            
            headers2 = {
                'client_id': ACCESS_ID,
                'access_token': token,
                'sign': sign2,
                't': t2,
                'sign_method': 'HMAC-SHA256',
            }
            
            resp2 = requests.get(base_url + path2, headers=headers2, timeout=10)
            devices_result = resp2.json()
            
            return {
                "status": "✅ Token OK",
                "devices": devices_result.get('msg', f"{len(devices_result.get('result', []))} dispositivos") if devices_result.get('success') else devices_result.get('msg', 'Erro')[:50]
            }
        else:
            return {"status": f"❌ {result.get('msg', 'Erro')[:40]}"}
    except Exception as e:
        return {"status": f"❌ {str(e)[:40]}"}

print("=" * 70)
print("   🌐 Testando Todos os Endpoints Tuya")
print("=" * 70)
print()

for name, url in ENDPOINTS.items():
    print(f"🔍 {name}: {url}")
    result = test_endpoint(name, url)
    print(f"   Token: {result['status']}")
    if 'devices' in result:
        print(f"   Devices: {result['devices']}")
    print()
