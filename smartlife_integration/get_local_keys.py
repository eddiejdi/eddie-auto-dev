#!/usr/bin/env python3
"""
Tenta obter Local Keys dos dispositivos descobertos.
"""
import json
import time
import hmac
import hashlib
import requests

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
BASE_URL = "https://openapi.tuyaus.com"

# Dispositivos descobertos
DEVICE_IDS = [
    "eb1b674c9f7a457346tsjz",
    "ebf17e68a06f66afef0l8i",
    "ebe81653601e425719xzt2",
    "eb3adbc9a153f0bd9cvuyo",
    "eb616ff67b859bf335vfzj"
]

def api_request(method, path, token=None, body=None):
    t = str(int(time.time() * 1000))
    body_str = json.dumps(body) if body else ""
    content_sha256 = hashlib.sha256(body_str.encode() if body_str else b"").hexdigest()
    string_to_sign = f"{method}\n{content_sha256}\n\n{path}"
    
    message = ACCESS_ID
    if token:
        message += token
    message += t + string_to_sign
    
    sign = hmac.new(ACCESS_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest().upper()
    
    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }
    if token:
        headers["access_token"] = token
    
    url = BASE_URL + path
    if method == "GET":
        return requests.get(url, headers=headers, timeout=15).json()
    else:
        return requests.post(url, headers=headers, json=body, timeout=15).json()

print("=" * 60)
print("   🔑 Obtendo Local Keys dos Dispositivos")
print("=" * 60)
print()

# 1. Obter token
result = api_request("GET", "/v1.0/token?grant_type=1")
if not result.get("success"):
    print(f"❌ Erro token: {result}")
    exit(1)

token = result["result"]["access_token"]
print("✅ Token obtido!")
print()

# 2. Tentar obter info de cada dispositivo
print("📱 Buscando informações dos dispositivos...")
print()

devices_with_keys = []

for dev_id in DEVICE_IDS:
    print(f"🔍 Device: {dev_id}...", end=" ")
    
    # Tentar obter detalhes do dispositivo
    result = api_request("GET", f"/v1.0/devices/{dev_id}", token)
    
    if result.get("success"):
        data = result.get("result", {})
        name = data.get("name", "Unknown")
        local_key = data.get("local_key", "")
        category = data.get("category", "")
        
        print(f"✅ {name}")
        if local_key:
            print(f"      Local Key: {local_key}")
            devices_with_keys.append({
                "id": dev_id,
                "name": name,
                "local_key": local_key,
                "category": category
            })
        else:
            print(f"      ⚠️ Sem Local Key (dispositivo não vinculado)")
    else:
        msg = result.get("msg", "Erro")
        print(f"❌ {msg[:40]}")

print()
print("=" * 60)

if devices_with_keys:
    print(f"\n✅ Obtidas {len(devices_with_keys)} Local Keys!\n")
    
    with open("config/devices_with_keys.json", "w") as f:
        json.dump(devices_with_keys, f, indent=2)
    print("💾 Salvo em config/devices_with_keys.json")
else:
    print("\n⚠️ Nenhuma Local Key obtida.")
    print("Os dispositivos precisam estar vinculados ao projeto Tuya.")
