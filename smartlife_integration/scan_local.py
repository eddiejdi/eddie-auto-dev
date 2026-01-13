#!/usr/bin/env python3
"""
Scan local da rede para encontrar dispositivos Tuya.
Não precisa de credenciais cloud - descobre dispositivos na rede local.
"""
import socket
import json
from datetime import datetime

print("=" * 60)
print("   🔍 Scan Local de Dispositivos Tuya/SmartLife")
print("=" * 60)
print()
print("Escaneando a rede local em busca de dispositivos...")
print("(Dispositivos Tuya se anunciam nas portas UDP 6666, 6667)")
print()

# Tentar importar tinytuya para scan
try:
    import tinytuya
    
    print("📡 Iniciando scan (aguarde até 30 segundos)...")
    print()
    
    # Scan na rede
    devices = tinytuya.deviceScan(verbose=True, maxretry=4, byID=True)
    
    if devices:
        print()
        print(f"✅ Encontrados {len(devices)} dispositivos na rede local!")
        print()
        
        device_list = []
        for dev_id, info in devices.items():
            print(f"📱 Dispositivo encontrado:")
            print(f"   ID: {dev_id}")
            print(f"   IP: {info.get('ip', 'N/A')}")
            print(f"   Versão: {info.get('version', 'N/A')}")
            print(f"   Product Key: {info.get('productKey', 'N/A')}")
            print()
            
            device_list.append({
                "id": dev_id,
                "ip": info.get('ip'),
                "version": info.get('version'),
                "productKey": info.get('productKey'),
                "discovered_at": datetime.now().isoformat()
            })
        
        # Salvar
        with open('config/local_devices.json', 'w') as f:
            json.dump(device_list, f, indent=2)
        
        print(f"💾 Dispositivos salvos em config/local_devices.json")
        print()
        print("⚠️ NOTA: Para controlar esses dispositivos localmente,")
        print("   você ainda precisa das 'Local Keys' que vêm do Tuya Cloud.")
        print("   Mas agora você tem os IDs dos dispositivos!")
        
    else:
        print()
        print("❌ Nenhum dispositivo encontrado na rede.")
        print()
        print("Possíveis causas:")
        print("  1. WSL não tem acesso à mesma rede WiFi dos dispositivos")
        print("  2. Dispositivos estão em outra subnet")
        print("  3. Firewall bloqueando UDP 6666/6667")
        print()
        print("💡 Tente executar o scan diretamente no Windows ou")
        print("   em uma máquina conectada à mesma rede WiFi.")

except ImportError:
    print("❌ TinyTuya não está instalado")
