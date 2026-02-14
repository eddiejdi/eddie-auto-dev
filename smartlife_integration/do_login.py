#!/usr/bin/env python3
"""Login SmartLife com credenciais fornecidas."""
import json
import os
import hashlib
import requests
from pathlib import Path

# Credenciais
USERNAME = "edenilson.teixeira@rpa4all.com"
PASSWORD = os.environ["TUYA_PASSWORD"]

# APIs SmartLife por região
SMARTLIFE_APIS = {
    "eu": "https://px1.tuyaeu.com",
    "us": "https://px1.tuyaus.com", 
    "cn": "https://px1.tuyacn.com"
}

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def login(username, password, region):
    """Tenta login na região especificada."""
    base_url = SMARTLIFE_APIS[region]
    password_hash = md5(password)
    
    login_url = f"{base_url}/homeassistant/auth.do"
    
    data = {
        "userName": username,
        "password": password_hash,
        "countryCode": "55",
        "bizType": "smartlife",
        "from": "tuya"
    }
    
    response = requests.post(login_url, data=data)
    return response.json()

def get_devices(access_token, region):
    """Lista dispositivos."""
    base_url = SMARTLIFE_APIS[region]
    url = f"{base_url}/homeassistant/skill"
    
    data = {
        "header": {
            "name": "Discovery",
            "namespace": "discovery",
            "payloadVersion": 1
        },
        "payload": {
            "accessToken": access_token
        }
    }
    
    response = requests.post(url, json=data)
    return response.json()

print("=" * 60)
print("   🏠 SmartLife - Login Automático")
print("=" * 60)
print()
print(f"📧 Usuário: {USERNAME}")
print()

# Tentar cada região
for region in ["us", "eu", "cn"]:
    print(f"🔐 Tentando região {region.upper()}...")
    
    result = login(USERNAME, PASSWORD, region)
    
    if result.get("access_token"):
        print(f"✅ LOGIN BEM-SUCEDIDO na região {region.upper()}!")
        print()
        
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token", "")
        
        # Salvar token
        config_dir = Path(__file__).parent / "config"
        config_dir.mkdir(exist_ok=True)
        
        token_file = config_dir / "smartlife_token.json"
        with open(token_file, 'w') as f:
            json.dump({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "region": region,
                "username": USERNAME
            }, f, indent=2)
        
        print(f"💾 Token salvo em: {token_file}")
        print()
        
        # Buscar dispositivos
        print("📱 Buscando dispositivos...")
        devices_result = get_devices(access_token, region)
        
        if "payload" in devices_result and "devices" in devices_result["payload"]:
            devices = devices_result["payload"]["devices"]
            print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")
            
            for i, device in enumerate(devices, 1):
                name = device.get("name", "Unknown")
                dev_id = device.get("id", "")
                dev_type = device.get("dev_type", "unknown")
                online = "🟢" if device.get("online", False) else "🔴"
                
                print(f"  {i}. {online} {name}")
                print(f"      ID: {dev_id}")
                print(f"      Tipo: {dev_type}")
                
                # Mostrar dados extras se disponíveis
                if device.get("data"):
                    print(f"      Estado: {device['data']}")
                print()
            
            # Salvar dispositivos
            devices_file = config_dir / "devices.json"
            with open(devices_file, 'w') as f:
                json.dump(devices, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Dispositivos salvos em: {devices_file}")
        else:
            print(f"⚠️  Resposta: {json.dumps(devices_result, indent=2)}")
        
        break
    else:
        error = result.get("errorMsg", result.get("msg", "Erro desconhecido"))
        print(f"   ❌ {error}")

else:
    print()
    print("❌ Não foi possível fazer login em nenhuma região.")
    print("   Verifique se o email e senha estão corretos.")
