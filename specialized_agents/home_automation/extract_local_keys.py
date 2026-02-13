#!/usr/bin/env python3
"""
Extrair local_keys dos devices Tuya descobertos.

Opções:
1. tinytuya.wizard() - pede credenciais Tuya Cloud
2. Broadcasting announcement - tinytuya pode extrair via broadcast
3. Manual - fornecer chave manualmente
"""

import json
import sys
import tinytuya
from pathlib import Path

def extract_keys_via_wizard():
    """Usar tinytuya.wizard() para extrair credenciais"""
    print("\n" + "=" * 70)
    print("🔑 Extraindo Local Keys via tinytuya.wizard()")
    print("=" * 70)
    print("""
Este wizard ajudará a obter as local keys dos seus devices.
Você precisará de:
  1. Número de celular/email da Smart Life
  2. Senha
  3. Região (Eastern America = 'us-e')

Após login, o wizard extrairá device_ids e local_keys automaticamente.
""")
    
    confirm = input("Continuar? [y/n] ").lower()
    if confirm != 'y':
        return None
    
    print("\nExecutando wizard...")
    try:
        # tinytuya.wizard() pede input interativo e salva em tinytuya_devices.json
        tinytuya.wizard()
        
        # Tentar carregar resultado
        wizard_file = Path("tinytuya_devices.json")
        if wizard_file.exists():
            with open(wizard_file, "r") as f:
                devices = json.load(f)
                print(f"\n✅ {len(devices)} devices extraídos!")
                return devices
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    return None


def extract_keys_local_broadcast():
    """Tentar extrair local_keys via broadcast (experimental)"""
    print("\n" + "=" * 70)
    print("📡 Extraindo Local Keys via Broadcast")
    print("=" * 70)
    print("Tentando descobrir local_keys via broadcast (tinytuya snapshot)...")
    
    try:
        # Fazer scan de novo
        devices = tinytuya.deviceScan(timeout=5)
        
        if devices:
            print(f"\n✅ {len(devices)} devices encontrados com dados")
            updated = {}
            for dev_id, info in devices.items():
                if info.get('key'):  # Se encontrou key no broadcast
                    updated[dev_id] = info
                    print(f"  {dev_id}: {info.get('name', 'Unknown')} -> {info.get('key')}")
            return updated if updated else None
    except Exception as e:
        print(f"❌ Erro durante broadcast: {e}")
    
    return None


def update_device_map_with_keys(devices_with_keys):
    """Atualizar device_map.json com as local_keys obtidas"""
    device_map_path = Path("agent_data/home_automation/device_map.json")
    
    if not device_map_path.exists():
        print("❌ device_map.json não encontrado")
        return
    
    with open(device_map_path, "r") as f:
        current_map = json.load(f)
    
    # Tentar mapear devices_with_keys para o device_map
    # Por IP ou por nome
    for device_id, device_config in current_map.items():
        ip = device_config.get("ip")
        
        # Procurar por IP nos devices com keys
        for dev_id, info in devices_with_keys.items():
            if info.get("ip") == ip:
                local_key = info.get("key") or info.get("local_key")
                if local_key and len(local_key) > 10:
                    current_map[device_id]["local_key"] = local_key
                    print(f"  ✅ {device_id}: local_key atualizar")
                    break
    
    # Salvar atualizado
    with open(device_map_path, "w") as f:
        json.dump(current_map, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ device_map.json atualizado")


def manual_entry():
    """Entry manual de local_keys"""
    device_map_path = Path("agent_data/home_automation/device_map.json")
    
    if not device_map_path.exists():
        print("❌ device_map.json não encontrado")
        return
    
    with open(device_map_path, "r") as f:
        device_map = json.load(f)
    
    print("\n" + "=" * 70)
    print("⌨️  Entry Manual de Local Keys")
    print("=" * 70)
    
    for device_id, config in device_map.items():
        if config["local_key"] == "0" * 16 or not config["local_key"]:
            print(f"\n{config['name']} ({config['ip']})")
            key = input("  Local key (16 caracteres hex, ou deixe em branco): ").strip()
            if key and len(key) >= 16:
                device_map[device_id]["local_key"] = key
                print(f"  ✅ Atualizado")
    
    with open(device_map_path, "w") as f:
        json.dump(device_map, f, indent=2, ensure_ascii=False)
    print(f"\n✅ device_map.json salvado")


def main():
    print("\n" + "=" * 70)
    print("🔑 Extrator de Local Keys - Tinytuya")
    print("=" * 70)
    print("""
Escolha o método para obter as local_keys:

1. tinytuya.wizard() - Requer credenciais Tuya Cloud (mais completo)
2. Broadcast - Tentar descobrir via broadcast na rede (rápido)
3. Manual - Entry manual das chaves (se souber)
4. Sair
""")
    
    choice = input("Escolha [1-4]: ").strip()
    
    if choice == "1":
        devices = extract_keys_via_wizard()
        if devices:
            update_device_map_with_keys(devices)
    elif choice == "2":
        devices = extract_keys_local_broadcast()
        if devices:
            update_device_map_with_keys(devices)
    elif choice == "3":
        manual_entry()
    elif choice == "4":
        print("Saindo...")
        return
    else:
        print("Opção inválida")


if __name__ == "__main__":
    main()
