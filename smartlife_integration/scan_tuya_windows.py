# -*- coding: utf-8 -*-
"""
Tuya Device Scanner - Execute no Windows!
==========================================

Este script descobre dispositivos Tuya/SmartLife na sua rede local.
Execute diretamente no Windows (não no WSL).

Como usar:
1. Abra o PowerShell ou CMD
2. Navegue até esta pasta
3. Execute: python scan_tuya_windows.py
"""
import subprocess
import sys

# Instalar tinytuya se necessário
try:
    import tinytuya
except ImportError:
    print("Instalando tinytuya...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tinytuya", "-q"])
    import tinytuya

import json
from datetime import datetime

print("=" * 60)
print("   🔍 Tuya/SmartLife Device Scanner")
print("=" * 60)
print()
print("Escaneando sua rede local por dispositivos Tuya...")
print("Certifique-se de que seu PC está na mesma rede WiFi")
print("que os dispositivos SmartLife.")
print()
print("Aguarde até 30 segundos...")
print()

# Fazer scan
devices = tinytuya.deviceScan(verbose=True, maxretry=4, byID=True)

print()
print("=" * 60)

if devices:
    print(f"\n✅ Encontrados {len(devices)} dispositivos!\n")
    
    device_list = []
    for dev_id, info in devices.items():
        print(f"📱 Dispositivo:")
        print(f"   ID: {dev_id}")
        print(f"   IP: {info.get('ip', 'N/A')}")
        print(f"   Versão protocolo: {info.get('version', 'N/A')}")
        print()
        
        device_list.append({
            "id": dev_id,
            "ip": info.get("ip"),
            "version": info.get("version"),
            "gwId": info.get("gwId"),
            "productKey": info.get("productKey"),
            "discovered": datetime.now().isoformat()
        })
    
    # Salvar em arquivo
    with open("discovered_devices.json", "w", encoding="utf-8") as f:
        json.dump(device_list, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Lista salva em: discovered_devices.json")
    print()
    print("=" * 60)
    print()
    print("PRÓXIMOS PASSOS:")
    print("-" * 40)
    print("Com os IDs dos dispositivos, você pode:")
    print("1. Tentar controle local (precisa da 'Local Key' do Tuya Cloud)")
    print("2. Usar os IDs para identificar no Tuya Developer Platform")
    print()
    
else:
    print("\n❌ Nenhum dispositivo encontrado.\n")
    print("Possíveis causas:")
    print("  1. PC não está na mesma rede WiFi dos dispositivos")
    print("  2. Firewall bloqueando portas UDP 6666, 6667, 7000")
    print("  3. Dispositivos estão offline")
    print()

input("\nPressione ENTER para sair...")
