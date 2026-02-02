#!/usr/bin/env python3
"""Teste de conexão com Tuya Cloud API."""

import json
import time
import hmac
import hashlib
import requests

config = {
    "access_id": "xgkk3vwjnpasrp34hpwf",
    "access_secret": "d0b4f1d738a141cbaf45eeffa6363820",
    "region": "us",
}

base_url = "https://openapi.tuyaus.com"
t = str(int(time.time() * 1000))
str_to_sign = config["access_id"] + t

sign = (
    hmac.new(
        config["access_secret"].encode("utf-8"),
        str_to_sign.encode("utf-8"),
        hashlib.sha256,
    )
    .hexdigest()
    .upper()
)

headers = {
    "client_id": config["access_id"],
    "sign": sign,
    "t": t,
    "sign_method": "HMAC-SHA256",
}

print("🔑 Testando conexão com Tuya Cloud API...")
print(f"   Region: {config['region']}")
print(f"   URL: {base_url}")
print()

response = requests.get(f"{base_url}/v1.0/token?grant_type=1", headers=headers)
result = response.json()

print(f"📋 Resposta: {json.dumps(result, indent=2)}")
print()

if result.get("success"):
    token = result["result"]["access_token"]
    print("✅ CONEXÃO OK!")
    print(f"   Token: {token[:20]}...")
    print(f"   Expira em: {result['result']['expire_time']}s")

    # Listar dispositivos
    print()
    print("📱 Listando dispositivos...")

    t2 = str(int(time.time() * 1000))
    str_to_sign2 = config["access_id"] + token + t2
    sign2 = (
        hmac.new(
            config["access_secret"].encode("utf-8"),
            str_to_sign2.encode("utf-8"),
            hashlib.sha256,
        )
        .hexdigest()
        .upper()
    )

    headers2 = {
        "client_id": config["access_id"],
        "access_token": token,
        "sign": sign2,
        "t": t2,
        "sign_method": "HMAC-SHA256",
    }

    response2 = requests.get(f"{base_url}/v1.0/users/devices", headers=headers2)
    devices_result = response2.json()

    print(f"📋 Dispositivos: {json.dumps(devices_result, indent=2)}")

    if devices_result.get("success") and devices_result.get("result"):
        print()
        print(f"✅ Encontrados {len(devices_result['result'])} dispositivos:")
        for dev in devices_result["result"]:
            status = "🟢" if dev.get("online") else "🔴"
            print(
                f"   {status} {dev.get('name', '?')} ({dev.get('category', '?')}) - ID: {dev['id'][:16]}..."
            )
else:
    print(f"❌ Erro: {result.get('msg', 'Desconhecido')}")
    print(f"   Código: {result.get('code')}")
