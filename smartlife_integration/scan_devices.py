#!/usr/bin/env python3
"""Script para escanear dispositivos Tuya na rede."""

import tinytuya

print("🔍 Escaneando dispositivos Tuya na rede local...")
print("   (Aguarde até 30 segundos)")
print()

devices = tinytuya.deviceScan(verbose=False, maxretry=3)

if devices:
    print(f"✅ Encontrados {len(devices)} dispositivos:")
    print()
    for ip, info in devices.items():
        dev_id = info.get("gwId", info.get("id", "unknown"))
        version = info.get("version", "3.3")
        print(f"  📱 IP: {ip}")
        print(f"     ID: {dev_id}")
        print(f"     Versão: {version}")
        print()
else:
    print("❌ Nenhum dispositivo encontrado na rede")
    print()
    print("Possíveis causas:")
    print("  - Dispositivos em subnet diferente")
    print("  - Firewall bloqueando UDP 6666/6667")
    print("  - WSL não tem acesso à mesma rede dos dispositivos")
