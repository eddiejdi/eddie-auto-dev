#!/usr/bin/env python3
"""
TinyTuya Wizard automatizado com credenciais já fornecidas.
"""

import json
from pathlib import Path

# Credenciais já fornecidas
API_KEY = "kjg5qhcsgd44uf8ppty8"
API_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
REGION = "us"  # Eastern America = us

# Criar arquivo tinytuya.json
config = {
    "apiKey": API_KEY,
    "apiSecret": API_SECRET,
    "apiRegion": REGION,
    "apiDeviceID": "all",
}

config_file = Path(__file__).parent / "tinytuya.json"
with open(config_file, "w") as f:
    json.dump(config, f, indent=2)

print(f"✅ Configuração salva em: {config_file}")
print()

# Agora usar TinyTuya Cloud
import tinytuya

print("🔌 Conectando ao Tuya Cloud...")
c = tinytuya.Cloud(apiRegion=REGION, apiKey=API_KEY, apiSecret=API_SECRET)

print("📱 Buscando dispositivos...")
devices = c.getdevices()

print(f"\n📋 Resultado: {type(devices)}")

if isinstance(devices, dict) and "Error" in str(devices):
    print(f"❌ Erro: {devices}")
elif isinstance(devices, list) and len(devices) > 0:
    print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")
    for d in devices:
        print(f"  📱 {d.get('name', 'Unknown')}")
        print(f"     ID: {d.get('id')}")
        print(f"     Key: {d.get('key', 'N/A')}")
        print(f"     Category: {d.get('category', 'N/A')}")
        print()

    # Salvar
    with open("config/devices.json", "w") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)
    print("💾 Dispositivos salvos em config/devices.json")
else:
    print("⚠️ Nenhum dispositivo encontrado ou erro.")
    print(f"   Resposta: {devices}")
    print()
    print("💡 Possíveis causas:")
    print("   1. Conta SmartLife não está vinculada ao projeto")
    print("   2. Data Center incorreto (sua conta pode estar em outro servidor)")
    print("   3. APIs não autorizadas no projeto")
