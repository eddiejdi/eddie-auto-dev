#!/usr/bin/env python3
"""Teste com TinyTuya Cloud."""

import tinytuya
import json

print("🔌 Testando TinyTuya Cloud...")
print()

# Configurar Cloud
c = tinytuya.Cloud(
    apiRegion="us",
    apiKey="kjg5qhcsgd44uf8ppty8",
    apiSecret="5a9be7cf8a514ce39112b53045c4b96f",
)

print("📱 Buscando dispositivos...")
devices = c.getdevices()

if devices:
    print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")
    for d in devices:
        print(f"  - {d.get('name', 'Unknown')}")
        print(f"    ID: {d.get('id')}")
        print(f"    Key: {d.get('key', 'N/A')}")
        print()

    # Salvar
    with open("config/devices_tinytuya.json", "w") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)
    print("💾 Salvo em config/devices_tinytuya.json")
else:
    print(f"❌ Nenhum dispositivo ou erro: {devices}")
