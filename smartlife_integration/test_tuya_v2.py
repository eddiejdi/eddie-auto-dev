#!/usr/bin/env python3
"""
Teste de conexão Tuya Cloud - Método correto de assinatura.
Baseado na documentação oficial: https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4
"""

import json
import time
import hmac
import hashlib
import requests

# Credenciais
ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
BASE_URL = "https://openapi.tuyaus.com"


def calc_sign(client_id, secret, t, access_token="", nonce="", string_to_hash=""):
    """
    Calcula a assinatura conforme documentação Tuya.
    Sign = HMAC-SHA256(ClientID + [AccessToken] + Timestamp + Nonce + StringToSign, secret).toUpperCase()
    """
    message = client_id
    if access_token:
        message += access_token
    message += t
    if nonce:
        message += nonce
    message += string_to_hash

    sign = (
        hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        .hexdigest()
        .upper()
    )

    return sign


def get_string_to_sign(method, path, headers_to_sign="", body=""):
    """
    Gera a string para assinatura.
    StringToSign = HTTPMethod + "\n" + Content-SHA256 + "\n" + Headers + "\n" + URL
    """
    # Content-SHA256
    if body:
        content_sha256 = hashlib.sha256(body.encode()).hexdigest()
    else:
        content_sha256 = hashlib.sha256(b"").hexdigest()

    string_to_sign = (
        method.upper() + "\n" + content_sha256 + "\n" + headers_to_sign + "\n" + path
    )

    return string_to_sign


def get_token():
    """Obtém token de acesso."""
    method = "GET"
    path = "/v1.0/token?grant_type=1"
    t = str(int(time.time() * 1000))

    # Calcular string para assinar
    string_to_sign = get_string_to_sign(method, path)

    # Calcular assinatura
    sign = calc_sign(ACCESS_ID, ACCESS_SECRET, t, string_to_hash=string_to_sign)

    headers = {
        "client_id": ACCESS_ID,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json",
    }

    url = BASE_URL + path
    print(f"🔗 URL: {url}")
    print(f"📝 String to sign: {repr(string_to_sign)}")
    print(f"🔐 Sign: {sign}")
    print()

    response = requests.get(url, headers=headers)
    return response.json()


print("=" * 60)
print("   🔌 Tuya Cloud API - Teste v2")
print("=" * 60)
print()
print(f"📋 Access ID: {ACCESS_ID}")
print(f"📋 Endpoint: {BASE_URL}")
print()

print("🔑 Obtendo token...")
print("-" * 40)
result = get_token()

print(f"📋 Resposta: {json.dumps(result, indent=2)}")
print()

if result.get("success"):
    print("✅ CONEXÃO OK!")
    token = result["result"]["access_token"]
    print(f"   Token: {token[:30]}...")
else:
    print(f"❌ Erro: {result.get('msg')}")
    print(f"   Código: {result.get('code')}")
