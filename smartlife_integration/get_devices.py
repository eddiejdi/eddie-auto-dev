#!/usr/bin/env python3
"""
Tuya Cloud API - Obter dispositivos vinculados.
"""
import json
import time
import hmac
import hashlib
import requests
from pathlib import Path

# Credenciais
ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
BASE_URL = "https://openapi.tuyaus.com"

def calc_sign(client_id, secret, t, access_token="", string_to_hash=""):
    """Calcula a assinatura."""
    message = client_id
    if access_token:
        message += access_token
    message += t
    message += string_to_hash
    
    sign = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    return sign

def get_string_to_sign(method, path, body=""):
    """Gera a string para assinatura."""
    if body:
        content_sha256 = hashlib.sha256(body.encode()).hexdigest()
    else:
        content_sha256 = hashlib.sha256(b"").hexdigest()
    
    return method.upper() + "\n" + content_sha256 + "\n" + "\n" + path

def api_request(method, path, token=None, body=None):
    """Faz requisição à API Tuya."""
    t = str(int(time.time() * 1000))
    body_str = json.dumps(body) if body else ""
    
    string_to_sign = get_string_to_sign(method, path, body_str)
    sign = calc_sign(ACCESS_ID, ACCESS_SECRET, t, access_token=token or "", string_to_hash=string_to_sign)
    
    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        't': t,
        'sign_method': 'HMAC-SHA256',
        'Content-Type': 'application/json'
    }
    
    if token:
        headers['access_token'] = token
    
    url = BASE_URL + path
    
    if method.upper() == "GET":
        response = requests.get(url, headers=headers)
    else:
        response = requests.post(url, headers=headers, json=body)
    
    return response.json()

print("=" * 60)
print("   🏠 Tuya Cloud - Buscar Dispositivos")
print("=" * 60)
print()

# 1. Obter token
print("🔑 Obtendo token...")
result = api_request("GET", "/v1.0/token?grant_type=1")

if not result.get('success'):
    print(f"❌ Erro: {result.get('msg')}")
    exit(1)

token = result['result']['access_token']
uid = result['result']['uid']
print(f"✅ Token obtido! UID: {uid}")
print()

# 2. Listar usuários vinculados
print("👥 Buscando usuários vinculados...")
users_result = api_request("GET", "/v1.0/users", token)

if users_result.get('success'):
    print(f"   Usuários: {users_result.get('result', [])}")
else:
    print(f"   Info: {users_result.get('msg')}")

# 3. Buscar dispositivos do usuário logado
print()
print("📱 Buscando dispositivos...")
devices_result = api_request("GET", f"/v1.0/users/{uid}/devices", token)

if devices_result.get('success'):
    devices = devices_result.get('result', [])
    print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")
    
    for i, device in enumerate(devices, 1):
        name = device.get('name', 'Unknown')
        dev_id = device.get('id', '')
        category = device.get('category', 'unknown')
        product_name = device.get('product_name', '')
        online = "🟢" if device.get('online', False) else "🔴"
        local_key = device.get('local_key', '')
        ip = device.get('ip', 'N/A')
        
        print(f"  {i}. {online} {name}")
        print(f"      Produto: {product_name}")
        print(f"      ID: {dev_id}")
        print(f"      Categoria: {category}")
        if local_key:
            print(f"      Local Key: {local_key}")
        print(f"      IP: {ip}")
        print()
    
    # Salvar
    config_dir = Path(__file__).parent / "config"
    config_dir.mkdir(exist_ok=True)
    
    with open(config_dir / "devices.json", 'w') as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)
    print(f"💾 Dispositivos salvos em config/devices.json")
    
else:
    print(f"⚠️  Erro: {devices_result.get('msg')}")
    print(f"   Código: {devices_result.get('code')}")
    
    if devices_result.get('code') == 2017:
        print()
        print("💡 Você precisa vincular sua conta SmartLife ao projeto!")
        print("   1. Acesse platform.tuya.com")
        print("   2. Vá em 'Devices' > 'Link Tuya App Account'")
        print("   3. Escaneie o QR code com o app SmartLife no celular")
        print("      (Perfil > Configurações > Vincular conta de terceiros)")
