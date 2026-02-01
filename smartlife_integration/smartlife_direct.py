#!/usr/bin/env python3
"""
Controle SmartLife/Tuya via API não-oficial (método Home Assistant).
Usa a mesma API que o app SmartLife usa internamente.
"""

import json
import hashlib
import time
import requests
from pathlib import Path

# Credenciais SmartLife
USERNAME = "edenilson.adm@gmail.com"
PASSWORD = "Eddie_88_tp!"
COUNTRY_CODE = "55"  # Brasil

# APIs SmartLife (mesmas que o app usa)
TUYA_ENDPOINTS = {
    "az": {"url": "https://a1.tuyaus.com", "region": "AZ"},  # Arizona (US West)
    "ay": {"url": "https://a1.tuyaus.com", "region": "AY"},  # US
    "us": {"url": "https://a1.tuyaus.com", "region": "US"},  # US
    "eu": {"url": "https://a1.tuyaeu.com", "region": "EU"},  # Europe
    "cn": {"url": "https://a1.tuyacn.com", "region": "CN"},  # China
}

# Client IDs dos apps oficiais
SMARTLIFE_CLIENT = {
    "client_id": "ekmnwp9f5pnh3trdtpgy",
    "secret": "r3me7ghmxjevrvnpemwmhw3fxtacphyg",
    "schema": "smartlife",
}

TUYA_CLIENT = {
    "client_id": "3fjrekuxank9eaej3gcx",
    "secret": "vay9v5r54ypxey9vy58t5qfmrv9xatnf",
    "schema": "tuyaSmart",
}


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def login_smartlife(username, password, country_code, region_key, client):
    """Login usando API interna do SmartLife."""
    endpoint = TUYA_ENDPOINTS[region_key]
    base_url = endpoint["url"]

    # Hash da senha
    password_hash = md5(password)

    # Timestamp
    t = int(time.time())

    # Construir request
    url = f"{base_url}/v1.0/iot-01/associated-users/actions/authorized-login"

    headers = {
        "Content-Type": "application/json",
    }

    # Tentar método 1: API antiga
    data = {
        "countryCode": country_code,
        "email": username,
        "password": password_hash,
        "ifencrypt": 1,
        "options": '{"group": 1}',
        "passwd_code_version": "2.0",
        "schema": client["schema"],
    }

    try:
        # Método antigo (Home Assistant style)
        old_url = f"{base_url}/homeassistant/auth.do"
        old_data = {
            "userName": username,
            "password": password_hash,
            "countryCode": country_code,
            "bizType": client["schema"],
            "from": "tuya",
        }

        response = requests.post(old_url, data=old_data, timeout=15)
        result = response.json()

        return result
    except Exception as e:
        return {"error": str(e)}


def get_devices_with_token(access_token, region_key):
    """Busca dispositivos usando token."""
    endpoint = TUYA_ENDPOINTS[region_key]
    base_url = endpoint["url"]

    url = f"{base_url}/homeassistant/skill"

    data = {
        "header": {"name": "Discovery", "namespace": "discovery", "payloadVersion": 1},
        "payload": {"accessToken": access_token},
    }

    try:
        response = requests.post(url, json=data, timeout=15)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


print("=" * 60)
print("   🏠 SmartLife - Login Direto (sem Tuya Developer)")
print("=" * 60)
print()
print(f"📧 Usuário: {USERNAME}")
print(f"🌍 País: Brasil (+{COUNTRY_CODE})")
print()

# Testar todas as regiões com ambos os clients
for client_name, client in [
    ("SmartLife", SMARTLIFE_CLIENT),
    ("Tuya Smart", TUYA_CLIENT),
]:
    print(f"\n📱 Testando app: {client_name}")
    print("-" * 40)

    for region_key in ["us", "az", "eu"]:
        print(f"   Região {region_key}...", end=" ")

        result = login_smartlife(USERNAME, PASSWORD, COUNTRY_CODE, region_key, client)

        if result.get("access_token"):
            print("✅ LOGIN OK!")
            print()
            print(f"🎉 SUCESSO! App: {client_name}, Região: {region_key}")
            print(f"   Token: {result['access_token'][:30]}...")

            # Salvar token
            config_dir = Path(__file__).parent / "config"
            config_dir.mkdir(exist_ok=True)

            with open(config_dir / "smartlife_token.json", "w") as f:
                json.dump(
                    {
                        "access_token": result["access_token"],
                        "refresh_token": result.get("refresh_token", ""),
                        "region": region_key,
                        "app": client_name,
                    },
                    f,
                    indent=2,
                )

            # Buscar dispositivos
            print()
            print("📱 Buscando dispositivos...")
            devices_result = get_devices_with_token(result["access_token"], region_key)

            if "payload" in devices_result and "devices" in devices_result["payload"]:
                devices = devices_result["payload"]["devices"]
                print(f"\n✅ Encontrados {len(devices)} dispositivos!\n")

                for d in devices:
                    name = d.get("name", "Unknown")
                    dev_id = d.get("id", "")
                    dev_type = d.get("dev_type", "")
                    online = "🟢" if d.get("online") else "🔴"

                    print(f"   {online} {name}")
                    print(f"      ID: {dev_id}")
                    print(f"      Tipo: {dev_type}")
                    print()

                # Salvar dispositivos
                with open(config_dir / "devices.json", "w") as f:
                    json.dump(devices, f, indent=2, ensure_ascii=False)
                print("💾 Dispositivos salvos!")
            else:
                print(f"   Resposta: {devices_result}")

            exit(0)
        else:
            error = result.get("errorMsg", result.get("msg", result.get("error", "?")))
            print(f"❌ {str(error)[:35]}")

print()
print("=" * 60)
print("❌ Não foi possível fazer login em nenhuma combinação.")
