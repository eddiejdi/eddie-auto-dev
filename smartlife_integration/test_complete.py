#!/usr/bin/env python3
"""
Método alternativo: Usar a API Smart Home PaaS com as credenciais existentes.
Tenta várias combinações de endpoints.
"""
import json
import time
import hmac
import hashlib
import requests
import uuid

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"

# Todos os endpoints possíveis
ENDPOINTS = [
    ("us-east", "https://openapi.tuyaus.com"),
    ("us-west", "https://openapi-ueaz.tuyaus.com"),
    ("eu-central", "https://openapi.tuyaeu.com"),
    ("eu-west", "https://openapi-weaz.tuyaeu.com"),
    ("india", "https://openapi.tuyain.com"),
]

def get_sign(payload, t, secret):
    """Gera assinatura."""
    str_to_sign = ACCESS_ID + t + payload
    return hmac.new(secret.encode(), str_to_sign.encode(), hashlib.sha256).hexdigest().upper()

def api_request(base_url, method, path, token=None, body=None):
    """Faz request para a API Tuya."""
    t = str(int(time.time() * 1000))
    
    # Calcular hash do body
    body_str = json.dumps(body) if body else ""
    content_sha256 = hashlib.sha256(body_str.encode() if body_str else b"").hexdigest()
    
    # String para assinar
    string_to_sign = f"{method}\n{content_sha256}\n\n{path}"
    
    # Calcular sign
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
        "Content-Type": "application/json"
    }
    
    if token:
        headers["access_token"] = token
    
    url = base_url + path
    
    if method == "GET":
        resp = requests.get(url, headers=headers, timeout=15)
    else:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
    
    return resp.json()

print("=" * 60)
print("   🔌 Tuya API - Teste Completo")
print("=" * 60)
print()

# Testar cada endpoint
for name, base_url in ENDPOINTS:
    print(f"\n🌐 Testando: {name}")
    print("-" * 40)
    
    # 1. Obter token
    result = api_request(base_url, "GET", "/v1.0/token?grant_type=1")
    
    if not result.get("success"):
        print(f"   ❌ Token: {result.get('msg', 'Erro')[:40]}")
        continue
    
    token = result["result"]["access_token"]
    uid = result["result"]["uid"]
    print(f"   ✅ Token OK! UID: {uid[:20]}...")
    
    # 2. Tentar várias APIs de dispositivos
    apis_to_try = [
        f"/v1.0/users/{uid}/devices",
        "/v1.0/iot-01/associated-users",
        "/v1.0/iot-03/devices",
        f"/v1.0/token/{uid}/devices",
        "/v2.0/cloud/thing/device",
    ]
    
    for api_path in apis_to_try:
        result = api_request(base_url, "GET", api_path, token)
        
        if result.get("success"):
            data = result.get("result", [])
            if isinstance(data, list) and len(data) > 0:
                print(f"   ✅ {api_path}: {len(data)} items!")
                print(f"      Dados: {json.dumps(data[:2], indent=2)[:200]}...")
            elif data:
                print(f"   ✅ {api_path}: Dados encontrados")
                print(f"      {json.dumps(data, indent=2)[:150]}...")
        else:
            msg = result.get("msg", "?")[:30]
            # Não mostrar erros de "uri path invalid" para não poluir
            if "uri path invalid" not in msg:
                print(f"   ⚠️ {api_path}: {msg}")

print()
print("=" * 60)
print()
print("Se nenhuma API retornou dispositivos, a conta SmartLife")
print("precisa ser vinculada ao projeto via QR Code no site.")
print()
print("ALTERNATIVA: Execute o scan local no WINDOWS (não WSL)")
print("para descobrir os dispositivos na sua rede WiFi.")
