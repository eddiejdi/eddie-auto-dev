#!/usr/bin/env python3
"""Teste de conexão com as novas credenciais Tuya Cloud."""

import json
import time
import hmac
import hashlib
import requests
from pathlib import Path

# Carregar credenciais
config_file = Path(__file__).parent / "config" / "tuya_cloud.json"
with open(config_file) as f:
    config = json.load(f)

ACCESS_ID = config["access_id"]
ACCESS_SECRET = config["access_secret"]
REGION = config["region"]

# URLs por região
ENDPOINTS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}

BASE_URL = ENDPOINTS.get(REGION, ENDPOINTS["us"])


def get_token():
    """Obtém token de acesso."""
    t = str(int(time.time() * 1000))

    # String para assinar (sem token)
    str_to_sign = ACCESS_ID + t

    # Calcular assinatura
    sign = (
        hmac.new(
            ACCESS_SECRET.encode("utf-8"), str_to_sign.encode("utf-8"), hashlib.sha256
        )
        .hexdigest()
        .upper()
    )

    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }

    response = requests.get(f"{BASE_URL}/v1.0/token?grant_type=1", headers=headers)
    return response.json()


def get_devices(token):
    """Lista dispositivos."""
    t = str(int(time.time() * 1000))

    # String para assinar (com token)
    str_to_sign = ACCESS_ID + token + t

    sign = (
        hmac.new(
            ACCESS_SECRET.encode("utf-8"), str_to_sign.encode("utf-8"), hashlib.sha256
        )
        .hexdigest()
        .upper()
    )

    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }

    # Listar usuários vinculados primeiro
    response = requests.get(f"{BASE_URL}/v1.0/apps/link-users", headers=headers)
    users_result = response.json()

    if users_result.get("success") and users_result.get("result"):
        print(f"📱 Usuários vinculados: {len(users_result['result'])}")

        all_devices = []
        for user in users_result["result"]:
            uid = user.get("uid")
            print(f"   - UID: {uid}")

            # Buscar dispositivos do usuário
            t2 = str(int(time.time() * 1000))
            str_to_sign2 = ACCESS_ID + token + t2
            sign2 = (
                hmac.new(
                    ACCESS_SECRET.encode("utf-8"),
                    str_to_sign2.encode("utf-8"),
                    hashlib.sha256,
                )
                .hexdigest()
                .upper()
            )

            headers2 = {
                "client_id": ACCESS_ID,
                "access_token": token,
                "sign": sign2,
                "t": t2,
                "sign_method": "HMAC-SHA256",
            }

            devices_resp = requests.get(
                f"{BASE_URL}/v1.0/users/{uid}/devices", headers=headers2
            )
            devices_result = devices_resp.json()

            if devices_result.get("success") and devices_result.get("result"):
                all_devices.extend(devices_result["result"])

        return {"success": True, "devices": all_devices}
    else:
        return {
            "success": False,
            "error": users_result.get("msg", "No users"),
            "response": users_result,
        }


print("=" * 60)
print("   🔌 Tuya Cloud API - Teste de Conexão")
print("=" * 60)
print()
print("📋 Configuração:")
print(f"   Access ID: {ACCESS_ID[:10]}...")
print(f"   Region: {REGION}")
print(f"   Endpoint: {BASE_URL}")
print()

# 1. Obter token
print("🔑 Obtendo token de acesso...")
token_result = get_token()

if token_result.get("success"):
    token = token_result["result"]["access_token"]
    expire = token_result["result"]["expire_time"]

    print("✅ Token obtido com sucesso!")
    print(f"   Token: {token[:20]}...")
    print(f"   Expira em: {expire}s")
    print()

    # Salvar token
    token_file = Path(__file__).parent / "config" / "token.json"
    with open(token_file, "w") as f:
        json.dump(
            {
                "access_token": token,
                "refresh_token": token_result["result"].get("refresh_token", ""),
                "expire_time": expire,
                "timestamp": time.time(),
            },
            f,
            indent=2,
        )
    print(f"💾 Token salvo em: {token_file}")
    print()

    # 2. Listar dispositivos
    print("📱 Buscando dispositivos...")
    devices_result = get_devices(token)

    if devices_result.get("success"):
        devices = devices_result["devices"]
        print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")

        for i, device in enumerate(devices, 1):
            name = device.get("name", "Unknown")
            dev_id = device.get("id", "")
            category = device.get("category", "unknown")
            online = "🟢" if device.get("online", False) else "🔴"
            local_key = device.get("local_key", "")
            ip = device.get("ip", "N/A")

            print(f"  {i}. {online} {name}")
            print(f"      ID: {dev_id}")
            print(f"      Categoria: {category}")
            print(
                f"      Local Key: {local_key[:8]}..."
                if local_key
                else "      Local Key: N/A"
            )
            print(f"      IP: {ip}")
            print()

        # Salvar dispositivos
        devices_file = Path(__file__).parent / "config" / "devices.json"
        with open(devices_file, "w") as f:
            json.dump(devices, f, indent=2, ensure_ascii=False)
        print(f"💾 Dispositivos salvos em: {devices_file}")

    else:
        print(f"⚠️  Erro ao buscar dispositivos: {devices_result.get('error')}")
        print(
            f"   Resposta: {json.dumps(devices_result.get('response', {}), indent=2)}"
        )
        print()
        print("💡 Você precisa vincular sua conta SmartLife ao projeto!")
        print("   1. No Tuya IoT Platform, vá em Devices > Link Tuya App Account")
        print("   2. Escaneie o QR code com o app SmartLife")

else:
    print(f"❌ Erro ao obter token: {token_result.get('msg', 'Unknown error')}")
    print(f"   Código: {token_result.get('code')}")
    print(f"   Resposta completa: {json.dumps(token_result, indent=2)}")
