#!/usr/bin/env python3
"""
Usa tuya-iot-py-sdk para tentar obter Local Keys.
"""

from tuya_iot import TuyaOpenAPI, TUYA_LOGGER
import logging

# Desabilitar logs verbosos
TUYA_LOGGER.setLevel(logging.WARNING)

ACCESS_ID = "kjg5qhcsgd44uf8ppty8"
ACCESS_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"

# Dispositivos descobertos
DEVICE_IDS = [
    "eb1b674c9f7a457346tsjz",
    "ebf17e68a06f66afef0l8i",
    "ebe81653601e425719xzt2",
    "eb3adbc9a153f0bd9cvuyo",
    "eb616ff67b859bf335vfzj",
]

print("=" * 60)
print("   🔌 Tuya IoT SDK - Teste")
print("=" * 60)
print()

# Testar diferentes endpoints
ENDPOINTS = [
    ("US", "https://openapi.tuyaus.com"),
    ("EU", "https://openapi.tuyaeu.com"),
    ("IN", "https://openapi.tuyain.com"),
]

for region, endpoint in ENDPOINTS:
    print(f"\n🌐 Testando região: {region}")
    print("-" * 40)

    try:
        api = TuyaOpenAPI(endpoint, ACCESS_ID, ACCESS_SECRET)
        response = api.connect()

        if response.get("success"):
            print("   ✅ Conectado!")

            # Tentar buscar dispositivos
            for dev_id in DEVICE_IDS[:2]:  # Testar só 2
                result = api.get(f"/v1.0/devices/{dev_id}")
                if result.get("success"):
                    data = result.get("result", {})
                    print(
                        f"   📱 {data.get('name', dev_id)}: Local Key = {data.get('local_key', 'N/A')}"
                    )
                else:
                    print(f"   ⚠️ {dev_id}: {result.get('msg', '?')[:30]}")
        else:
            print(f"   ❌ Erro: {response.get('msg', '?')[:40]}")

    except Exception as e:
        print(f"   ❌ Exceção: {str(e)[:40]}")

print()
print("=" * 60)
