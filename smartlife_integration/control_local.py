#!/usr/bin/env python3
"""
Controle local de dispositivos Tuya SEM Local Key.
Funciona para alguns dispositivos com protocolo 3.1/3.3.
"""
import tinytuya
import json
from pathlib import Path

# Dispositivos descobertos
DEVICES = [
    {"id": "eb1b674c9f7a457346tsjz", "ip": "192.168.15.5", "version": "3.4"},
    {"id": "ebf17e68a06f66afef0l8i", "ip": "192.168.15.11", "version": "3.5"},
    {"id": "ebe81653601e425719xzt2", "ip": "192.168.15.12", "version": "3.4"},
    {"id": "eb3adbc9a153f0bd9cvuyo", "ip": "192.168.15.14", "version": "3.4"},
    {"id": "eb616ff67b859bf335vfzj", "ip": "192.168.15.16", "version": "3.4"},
]

print("=" * 60)
print("   🏠 Controle Local de Dispositivos Tuya")
print("=" * 60)
print()
print("⚠️  NOTA: Sem Local Key, comandos podem não funcionar.")
print("    Mas podemos tentar descobrir o status dos dispositivos.")
print()

# Carregar Local Keys se existirem
keys_file = Path("config/local_keys.json")
local_keys = {}
if keys_file.exists():
    with open(keys_file) as f:
        data = json.load(f)
        for d in data:
            local_keys[d["id"]] = d.get("key", "")

print("📱 Dispositivos encontrados:")
print("-" * 40)

for i, dev in enumerate(DEVICES, 1):
    dev_id = dev["id"]
    ip = dev["ip"]
    version = dev["version"]
    key = local_keys.get(dev_id, "")
    
    print(f"\n{i}. IP: {ip}")
    print(f"   ID: {dev_id}")
    print(f"   Versão: {version}")
    print(f"   Key: {'✅ ' + key[:8] + '...' if key else '❌ Não disponível'}")
    
    # Tentar conectar
    try:
        d = tinytuya.Device(dev_id, ip, key, version=version)
        d.set_socketTimeout(3)
        
        status = d.status()
        if status and "dps" in status:
            print(f"   Status: 🟢 Online")
            print(f"   DPS: {status['dps']}")
        elif status and "Error" in str(status):
            print(f"   Status: ⚠️ {status.get('Error', 'Erro')[:30]}")
        else:
            print(f"   Status: 🔴 Sem resposta")
    except Exception as e:
        print(f"   Status: ❌ {str(e)[:30]}")

print()
print("=" * 60)
print()
print("Para controlar os dispositivos, você precisa das Local Keys.")
print()
print("OPÇÕES para obter Local Keys:")
print("  1. Vincular conta SmartLife no Tuya Developer (precisa Data Center correto)")
print("  2. Usar ferramenta de extração do APK SmartLife")
print("  3. Interceptar tráfego do app com mitmproxy")
