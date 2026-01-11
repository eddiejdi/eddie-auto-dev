#!/usr/bin/env python3
"""
Conectar à Tuya Cloud usando credenciais da conta SmartLife.
Baseado no método do Home Assistant LocalTuya.
"""
import json
import requests
import time
import hashlib
import hmac
from pathlib import Path

# URLs da Tuya Cloud API
TUYA_CLOUD_URLS = {
    "cn": "https://openapi.tuyacn.com",
    "us": "https://openapi.tuyaus.com", 
    "eu": "https://openapi.tuyaeu.com",
    "in": "https://openapi.tuyain.com"
}


def get_tuya_token(access_id, access_secret, region="us"):
    """Obtém token de acesso da Tuya Cloud API."""
    base_url = TUYA_CLOUD_URLS.get(region, TUYA_CLOUD_URLS["us"])
    
    # Timestamp
    t = str(int(time.time() * 1000))
    
    # Sign string
    str_to_sign = access_id + t
    
    # HMAC-SHA256
    sign = hmac.new(
        access_secret.encode('utf-8'),
        str_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    headers = {
        "client_id": access_id,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    
    url = f"{base_url}/v1.0/token?grant_type=1"
    
    print(f"🔑 Obtendo token da Tuya Cloud ({region})...")
    response = requests.get(url, headers=headers)
    
    return response.json()


def list_devices(access_id, access_secret, access_token, region="us"):
    """Lista dispositivos da conta."""
    base_url = TUYA_CLOUD_URLS.get(region, TUYA_CLOUD_URLS["us"])
    
    t = str(int(time.time() * 1000))
    
    # Para requisições autenticadas, o sign inclui o token
    str_to_sign = access_id + access_token + t
    
    sign = hmac.new(
        access_secret.encode('utf-8'),
        str_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    headers = {
        "client_id": access_id,
        "access_token": access_token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256"
    }
    
    # Endpoint para listar dispositivos do usuário
    url = f"{base_url}/v1.0/users/devices"
    
    print("📱 Listando dispositivos...")
    response = requests.get(url, headers=headers)
    
    return response.json()


def control_device(access_id, access_secret, access_token, device_id, commands, region="us"):
    """
    Envia comando para um dispositivo.
    
    commands: lista de {"code": "switch", "value": true}
    """
    base_url = TUYA_CLOUD_URLS.get(region, TUYA_CLOUD_URLS["us"])
    
    t = str(int(time.time() * 1000))
    
    body = json.dumps({"commands": commands})
    
    # Para POST, o sign inclui body hash
    body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
    
    string_to_hash = (
        access_id + access_token + t + 
        "POST\n" +
        body_hash + "\n" +
        "\n" +  # empty headers
        f"/v1.0/devices/{device_id}/commands"
    )
    
    sign = hmac.new(
        access_secret.encode('utf-8'),
        string_to_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    headers = {
        "client_id": access_id,
        "access_token": access_token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json"
    }
    
    url = f"{base_url}/v1.0/devices/{device_id}/commands"
    
    print(f"📡 Enviando comando para {device_id}...")
    response = requests.post(url, headers=headers, data=body)
    
    return response.json()


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           Tuya Cloud API - Controle de Dispositivos             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  IMPORTANTE: Este método requer credenciais da Tuya IoT        ║
║  Platform, NÃO as credenciais do app SmartLife.                 ║
║                                                                  ║
║  Para obter as credenciais:                                     ║
║  1. Acesse: https://auth.tuya.com                               ║
║  2. Crie uma conta (ou use a existente)                         ║
║  3. Vá em Cloud Development > Create Cloud Project              ║
║  4. Anote o Access ID e Access Secret                           ║
║  5. Em "Link Device by App Account" vincule seu SmartLife       ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # Verificar se há config salva
    config_file = Path(__file__).parent / "config" / "tuya_cloud.json"
    
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        print(f"✅ Configuração encontrada: {config.get('access_id', '')[:8]}...")
    else:
        print("⚠️  Nenhuma configuração encontrada.\n")
        config = {
            "access_id": input("Access ID (da Tuya IoT Platform): ").strip(),
            "access_secret": input("Access Secret: ").strip(),
            "region": input("Região [us/eu/cn/in]: ").strip() or "us"
        }
        
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"\n💾 Salvo em: {config_file}")
    
    # Testar conexão
    result = get_tuya_token(
        config["access_id"],
        config["access_secret"], 
        config["region"]
    )
    
    print(f"\n📋 Resposta: {json.dumps(result, indent=2)}")
    
    if result.get("success"):
        token = result["result"]["access_token"]
        print(f"\n✅ Token obtido! Expira em {result['result']['expire_time']}s")
        
        # Listar dispositivos
        devices = list_devices(
            config["access_id"],
            config["access_secret"],
            token,
            config["region"]
        )
        
        print(f"\n📋 Dispositivos: {json.dumps(devices, indent=2)}")
    else:
        print(f"\n❌ Erro: {result.get('msg', 'Desconhecido')}")
        print("\nVerifique suas credenciais da Tuya IoT Platform.")


if __name__ == "__main__":
    main()
