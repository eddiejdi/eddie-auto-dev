#!/usr/bin/env python3
"""
Extração de local_keys via Tuya Cloud API
Usa Access ID e Secret já configurados
"""
import json
import time
import hashlib
import hmac
import requests

# Credenciais da API Tuya Cloud (já salvas anteriormente)
ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "4d40b1b8fbcc45fca96e96f64fb2c00d"
REGION = "us-e"  # Eastern America (us-e endpoint)

# Endpoints da API
API_BASE = "https://openapi-ueaz.tuyaus.com"  # Eastern America datacenter (correto)

def get_sign(client_id, secret, t, method="GET", path="", headers_str="", body_sha256=""):
    """Gera assinatura para requisições à API Tuya segundo a documentação oficial"""
    # Para body vazio, o SHA256 é sempre este valor
    if not body_sha256:
        body_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    # stringToSign = HTTPMethod + "\n" + Content-SHA256 + "\n" + Headers + "\n" + Url
    string_to_sign = f"{method}\n{body_sha256}\n{headers_str}\n{path}"
    
    # sign = HMAC-SHA256(client_id + t + stringToSign, secret).toUpperCase()
    str_to_hash = client_id + t + string_to_sign
    sign = hmac.new(
        secret.encode('utf-8'),
        str_to_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    return sign

def get_access_token():
    """Obtém access token da API Tuya"""
    t = str(int(time.time() * 1000))
    path = "/v1.0/token?grant_type=1"
    
    sign = get_sign(
        ACCESS_ID, 
        ACCESS_SECRET, 
        t,
        method="GET",
        path=path,
        headers_str="",  # Sem headers customizados
        body_sha256=""   # Body vazio
    )
    
    url = f"{API_BASE}{path}"
    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }
    
    print(f"🔐 Obtendo access token...")
    response = requests.get(url, headers=headers)
    result = response.json()
    
    if not result.get("success"):
        raise Exception(f"Erro ao obter token: {result}")
    
    token = result["result"]["access_token"]
    print(f"✓ Access token obtido")
    return token

def get_devices(access_token):
    """Lista todos os dispositivos da conta"""
    t = str(int(time.time() * 1000))
    path = "/v1.0/devices"
    
    # Para operações de serviço (não-token), a assinatura inclui access_token
    # sign = HMAC-SHA256(client_id + access_token + t + stringToSign, secret)
    body_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    string_to_sign = f"GET\n{body_sha256}\n\n{path}"
    str_to_hash = ACCESS_ID + access_token + t + string_to_sign
    
    sign = hmac.new(
        ACCESS_SECRET.encode('utf-8'),
        str_to_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    url = f"{API_BASE}{path}"
    headers = {
        "client_id": ACCESS_ID,
        "access_token": access_token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }
    
    print(f"\n📱 Listando dispositivos...")
    response = requests.get(url, headers=headers)
    result = response.json()
    
    if not result.get("success"):
        print(f"❌ Erro ao listar dispositivos: {result}")
        return []
    
    devices = result.get("result", [])
    print(f"✓ Encontrados {len(devices)} dispositivos na conta")
    return devices

def get_device_details(access_token, device_id):
    """Obtém detalhes de um dispositivo específico, incluindo local_key"""
    t = str(int(time.time() * 1000))
    path = f"/v1.0/devices/{device_id}"
    
    # Para operações de serviço (não-token), a assinatura inclui access_token
    body_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    string_to_sign = f"GET\n{body_sha256}\n\n{path}"
    str_to_hash = ACCESS_ID + access_token + t + string_to_sign
    
    sign = hmac.new(
        ACCESS_SECRET.encode('utf-8'),
        str_to_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().upper()
    
    url = f"{API_BASE}{path}"
    headers = {
        "client_id": ACCESS_ID,
        "access_token": access_token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }
    
    response = requests.get(url, headers=headers)
    result = response.json()
    
    if not result.get("success"):
        return None
    
    return result.get("result", {})

def main():
    print("🔑 Extraindo local_keys da Tuya Cloud API")
    print("=" * 60)
    
    try:
        # 1. Obter access token
        access_token = get_access_token()
        
        # 2. Listar dispositivos
        devices = get_devices(access_token)
        
        if not devices:
            print("\n⚠️  Nenhum dispositivo encontrado na conta")
            return 1
        
        # 3. Obter detalhes de cada dispositivo
        print("\n📋 Obtendo local_keys...")
        print("=" * 60)
        
        output = {}
        for device in devices:
            device_id = device.get("id")
            name = device.get("name", "Unknown")
            
            print(f"\nDispositivo: {name}")
            print(f"  ID: {device_id}")
            
            # Obter detalhes completos
            details = get_device_details(access_token, device_id)
            
            if details:
                local_key = details.get("local_key", "")
                ip = details.get("ip", "")
                
                output[device_id] = {
                    "id": device_id,
                    "name": name,
                    "local_key": local_key,
                    "ip": ip,
                    "online": details.get("online", False),
                    "category": details.get("category", ""),
                    "product_name": details.get("product_name", ""),
                }
                
                print(f"  Local Key: {local_key[:16]}..." if local_key else "  Local Key: (vazio)")
                print(f"  IP: {ip if ip else '(não disponível)'}")
                print(f"  Online: {details.get('online', False)}")
            else:
                print(f"  ⚠️  Não foi possível obter detalhes")
        
        # 4. Salvar resultado
        output_file = "tuya_devices_with_keys.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Dispositivos salvos em {output_file}")
        print("\n" + "=" * 60)
        
        # Estatísticas
        devices_with_keys = sum(1 for d in output.values() if d.get('local_key'))
        print(f"\nEstatísticas:")
        print(f"  Total de dispositivos: {len(output)}")
        print(f"  Com local_key: {devices_with_keys}")
        print(f"  Sem local_key: {len(output) - devices_with_keys}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
