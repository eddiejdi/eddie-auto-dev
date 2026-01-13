#!/usr/bin/env python3
"""Login SmartLife - Tentando múltiplas plataformas e formatos."""
import json
import hashlib
import requests
from pathlib import Path

# Credenciais
USERNAME = "edenilson.adm@gmail.com"
PASSWORD = "Eddie_88_tp!"

# APIs 
APIS = {
    "eu": "https://px1.tuyaeu.com",
    "us": "https://px1.tuyaus.com", 
    "cn": "https://px1.tuyacn.com"
}

# Plataformas/Apps para testar
PLATFORMS = ["smart_life", "tuyaSmart", "tuya", "smartlife", "az"]

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def try_login(username, password, region, platform):
    """Tenta login com combinação específica."""
    base_url = APIS[region]
    password_hash = md5(password)
    
    login_url = f"{base_url}/homeassistant/auth.do"
    
    data = {
        "userName": username,
        "password": password_hash,
        "countryCode": "55",
        "bizType": platform,
        "from": "tuya"
    }
    
    try:
        response = requests.post(login_url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

print("=" * 60)
print("   🏠 SmartLife - Testando Múltiplas Plataformas")
print("=" * 60)
print()
print(f"📧 Usuário: {USERNAME}")
print()

success = False

for region in ["us", "eu"]:
    if success:
        break
    print(f"\n🌍 Região: {region.upper()}")
    print("-" * 40)
    
    for platform in PLATFORMS:
        result = try_login(USERNAME, PASSWORD, region, platform)
        
        if result.get("access_token"):
            print(f"  ✅ {platform}: LOGIN OK!")
            
            access_token = result["access_token"]
            
            # Salvar
            config_dir = Path(__file__).parent / "config"
            config_dir.mkdir(exist_ok=True)
            
            token_file = config_dir / "smartlife_token.json"
            with open(token_file, 'w') as f:
                json.dump({
                    "access_token": access_token,
                    "refresh_token": result.get("refresh_token", ""),
                    "region": region,
                    "platform": platform,
                    "username": USERNAME
                }, f, indent=2)
            
            print(f"\n💾 Token salvo!")
            
            # Buscar dispositivos
            print("\n📱 Buscando dispositivos...")
            
            url = f"{APIS[region]}/homeassistant/skill"
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
            
            resp = requests.post(url, json=data)
            devices_result = resp.json()
            
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
                    print()
                
                # Salvar dispositivos
                devices_file = config_dir / "devices.json"
                with open(devices_file, 'w') as f:
                    json.dump(devices, f, indent=2, ensure_ascii=False)
                
                print(f"💾 Dispositivos salvos em: {devices_file}")
            else:
                print(f"   Resposta dispositivos: {devices_result}")
            
            success = True
            break
        else:
            error = result.get("errorMsg", result.get("msg", "?"))[:50]
            print(f"  ❌ {platform}: {error}")

if not success:
    print("\n" + "=" * 60)
    print("❌ Nenhuma combinação funcionou.")
    print()
    print("Alternativas:")
    print("  1. Verifique se o app é SmartLife ou Tuya Smart")
    print("  2. Tente redefinir a senha no app")
    print("  3. Use o método TinyTuya Cloud (precisa iot.tuya.com)")
