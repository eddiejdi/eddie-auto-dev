#!/usr/bin/env python3
"""
Login SmartLife usando a API correta.
Baseado em: https://github.com/rospogriern/localtuya
"""
import json
import os
import hashlib
import hmac
import time
import requests
from pathlib import Path

# Credenciais
USERNAME = "edenilson.teixeira@rpa4all.com"
PASSWORD = os.environ["TUYA_PASSWORD"]

# Constantes da API SmartLife/Tuya
TUYA_SMART_LIFE_APP = {
    "client_id": "ekmnwp9f5pnh3trdtpgy",  # Smart Life app
    "schema": "smartlife"
}

TUYA_SMART_APP = {
    "client_id": "3fjrekuxank9eaej3gcx",  # Tuya Smart app
    "schema": "tuyaSmart"
}

REGIONS = {
    "us": {"endpoint": "https://a1.tuyaus.com", "region": "us"},
    "eu": {"endpoint": "https://a1.tuyaeu.com", "region": "eu"},
    "cn": {"endpoint": "https://a1.tuyacn.com", "region": "cn"},
    "in": {"endpoint": "https://a1.tuyain.com", "region": "in"},
}

def get_token_sign(client_id, secret, access_token=""):
    """Gera assinatura para a API."""
    t = int(time.time() * 1000)
    message = client_id + str(t)
    if access_token:
        message = client_id + access_token + str(t)
    sign = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest().upper()
    return t, sign

def login_tuya_api(email, password, region_code, app_type="smartlife"):
    """Login usando API Tuya direta."""
    
    if app_type == "smartlife":
        app = TUYA_SMART_LIFE_APP
    else:
        app = TUYA_SMART_APP
    
    region = REGIONS.get(region_code, REGIONS["us"])
    endpoint = region["endpoint"]
    
    # Hash da senha
    password_hash = hashlib.md5(password.encode()).hexdigest()
    
    url = f"{endpoint}/v1.0/iot-01/associated-users/actions/authorized-login"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    body = {
        "username": email,
        "password": password_hash,
        "country_code": "55",
        "schema": app["schema"]
    }
    
    try:
        response = requests.post(url, json=body, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def login_home_assistant_api(email, password, region_code, app_type="smartlife"):
    """Login usando API Home Assistant (deprecated see docs/SECRETS_AGENT_USAGE.MD)."""
    
    endpoints = {
        "us": "https://px1.tuyaus.com",
        "eu": "https://px1.tuyaeu.com",
        "cn": "https://px1.tuyacn.com"
    }
    
    endpoint = endpoints.get(region_code, endpoints["us"])
    password_hash = hashlib.md5(password.encode()).hexdigest()
    
    url = f"{endpoint}/homeassistant/auth.do"
    
    data = {
        "userName": email,
        "password": password_hash,
        "countryCode": "55",
        "bizType": app_type,
        "from": "tuya"
    }
    
    try:
        response = requests.post(url, data=data, timeout=15)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

print("=" * 60)
print("   🏠 SmartLife/Tuya - Login Multi-método")
print("=" * 60)
print()
print(f"📧 Usuário: {USERNAME}")
print(f"⏰ Aguarde, testando diferentes métodos...")
print()

config_dir = Path(__file__).parent / "config"
config_dir.mkdir(exist_ok=True)

# Método 1: API Home Assistant (deprecated see docs/SECRETS_AGENT_USAGE.MD)
print("📡 Método 1: API Home Assistant (deprecated see docs/SECRETS_AGENT_USAGE.MD)")
print("-" * 40)

for region in ["us", "eu"]:
    for app_type in ["smart_life", "tuyaSmart"]:
        print(f"  Tentando {region}/{app_type}...", end=" ")
        result = login_home_assistant_api(USERNAME, PASSWORD, region, app_type)
        
        if result.get("access_token"):
            print("✅ OK!")
            
            with open(config_dir / "smartlife_token.json", 'w') as f:
                json.dump({
                    "method": "home_assistant_api",
                    "access_token": result["access_token"],
                    "refresh_token": result.get("refresh_token", ""),
                    "region": region,
                    "app_type": app_type,
                    "username": USERNAME
                }, f, indent=2)
            
            print(f"\n💾 Token salvo! Método: Home Assistant API")
            print(f"   Região: {region}, App: {app_type}")
            exit(0)
        else:
            error = result.get("errorMsg", result.get("msg", "?"))[:40]
            print(f"❌ {error}")

print()
print("📡 Método 2: API Tuya IoT (novo)")
print("-" * 40)

for region in ["us", "eu"]:
    for app_type in ["smartlife", "tuyaSmart"]:
        print(f"  Tentando {region}/{app_type}...", end=" ")
        result = login_tuya_api(USERNAME, PASSWORD, region, app_type)
        
        if result.get("success") and result.get("result"):
            print("✅ OK!")
            
            with open(config_dir / "smartlife_token.json", 'w') as f:
                json.dump({
                    "method": "tuya_iot_api",
                    "result": result["result"],
                    "region": region,
                    "app_type": app_type,
                    "username": USERNAME
                }, f, indent=2)
            
            print(f"\n💾 Token salvo! Método: Tuya IoT API")
            exit(0)
        else:
            error = str(result.get("msg", result.get("error", "?")))[:40]
            print(f"❌ {error}")

print()
print("=" * 60)
print("❌ Todos os métodos falharam.")
print()
print("🔍 Diagnóstico:")
print("   - Verifique se você usa o app 'Smart Life' ou 'Tuya Smart'")
print("   - Confirme se o email e senha estão corretos")
print("   - Tente fazer login no app para verificar")
print()
print("💡 Alternativa: TinyTuya Wizard (precisa criar conta em iot.tuya.com)")
