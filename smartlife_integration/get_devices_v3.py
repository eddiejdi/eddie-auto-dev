#!/usr/bin/env python3
"""
Tuya Cloud API - Assinatura corrigida para requisições com token.
"""

import json
import time
import hmac
import hashlib
import requests

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
BASE_URL = "https://openapi.tuyaus.com"


def calc_sign(client_id, secret, t, access_token="", string_to_hash=""):
    """
    Assinatura: HMAC-SHA256(client_id + [access_token] + t + stringToSign, secret)
    """
    message = client_id
    if access_token:
        message += access_token
    message += t
    message += string_to_hash

    sign = (
        hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        .hexdigest()
        .upper()
    )

    return sign


def get_string_to_sign(method, path, body=""):
    """StringToSign = method + \n + content-sha256 + \n + headers + \n + url"""
    content_sha256 = hashlib.sha256(body.encode() if body else b"").hexdigest()
    return f"{method.upper()}\n{content_sha256}\n\n{path}"


def get_token():
    """Obtém token."""
    path = "/v1.0/token?grant_type=1"
    t = str(int(time.time() * 1000))
    string_to_sign = get_string_to_sign("GET", path)
    sign = calc_sign(ACCESS_ID, ACCESS_SECRET, t, string_to_hash=string_to_sign)

    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }

    response = requests.get(BASE_URL + path, headers=headers)
    return response.json()


def api_get(path, token):
    """GET request com token."""
    t = str(int(time.time() * 1000))
    string_to_sign = get_string_to_sign("GET", path)
    sign = calc_sign(
        ACCESS_ID, ACCESS_SECRET, t, access_token=token, string_to_hash=string_to_sign
    )

    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
    }

    response = requests.get(BASE_URL + path, headers=headers)
    return response.json()


print("=" * 60)
print("   🏠 Tuya Cloud - Buscar Dispositivos v3")
print("=" * 60)
print()

# 1. Token
print("🔑 Obtendo token...")
result = get_token()
if not result.get("success"):
    print(f"❌ Erro: {result}")
    exit(1)

token = result["result"]["access_token"]
uid = result["result"]["uid"]
print(f"✅ Token OK! UID: {uid}")
print()

# 2. Listar usuários vinculados (Link Tuya App Account)
print("👥 Buscando contas vinculadas...")
linked = api_get("/v1.0/iot-01/associated-users", token)
print(f"   Resultado: {json.dumps(linked, indent=2)[:200]}")
print()

# 3. Tentar com outro endpoint
print("📱 Buscando dispositivos do projeto...")
devices_result = api_get(f"/v1.0/users/{uid}/devices", token)
print(f"   Resultado: {json.dumps(devices_result, indent=2)[:300]}")
print()

# 4. Tentar listar homes
print("🏠 Buscando homes...")
homes = api_get("/v1.0/homes", token)
print(f"   Resultado: {json.dumps(homes, indent=2)[:200]}")
print()

# 5. Listar devices por UID direto
print("📱 Tentando /v2.0/cloud/thing...")
things = api_get("/v2.0/cloud/thing/device", token)
print(f"   Resultado: {json.dumps(things, indent=2)[:200]}")
