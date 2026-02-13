#!/usr/bin/env python3
"""
Setup para integração Google Assistant com tinytuya.

Este script:
1. Escaneia rede para descobrir devices Tuya
2. Extrai local_keys (com ajuda do usuário)
3. Registra devices para controle via Google Assistant
"""

import sys
import json
import argparse
from pathlib import Path

# Adicionar projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from specialized_agents.home_automation.tinytuya_executor import TinyTuyaExecutor, get_executor


def scan_and_register():
    """Interativo: scan, extract, register"""
    print("\n" + "=" * 70)
    print("Google Assistant + Tinytuya Setup")
    print("=" * 70)
    
    executor = get_executor()
    
    # Step 1: Scan
    print("\n📡 Step 1: Scanning network para descobrir devices Tuya...")
    devices = executor.scan_network(force_refresh=True)
    
    if not devices:
        print("❌ Nenhum device encontrado. Certifique-se que:")
        print("  - Os devices estão na mesma rede Wi-Fi")
        print("  - Os devices foram pareados com Smart Life")
        return
    
    print(f"✅ Encontrados {len(devices)} devices")
    print("\nDevices descobertos:")
    for idx, (dev_id, info) in enumerate(devices.items(), 1):
        print(f"\n  [{idx}] {info.get('device_name', 'Unknown')}")
        print(f"      Device ID: {dev_id}")
        print(f"      IP: {info.get('ip')}")
        print(f"      Local Key: {info.get('local_key', 'DESCONHECIDA')}")
        print(f"      Version: {info.get('protocol_version', 3.4)}")
    
    # Step 2: Ask user to verify local_keys
    print("\n" + "-" * 70)
    print("⚠️  Local Keys")
    print("-" * 70)
    print("""
Se algum device mostra "local_key: DESCONHECIDA", você pode obter a chave:

1. Via Smart Life app (requer APK+mirror e extração manual)
2. Via Cloud Credentials JSON (se tiver acesso ao painel)
3. Via Android Debug Bridge (adb) em device Smart Life

Referência: https://github.com/jasonacox/tinytuya#getting-local-keys
""")
    
    # Step 3: Register devices
    print("\n" + "-" * 70)
    print("📝 Step 2: Registrar devices para Google Assistant")
    print("-" * 70)
    
    registered_count = 0
    for idx, (dev_id, info) in enumerate(devices.items(), 1):
        name = info.get('device_name', f'Device_{idx}')
        ip = info.get('ip')
        local_key = info.get('local_key', '')
        version = info.get('protocol_version', 3.4)
        
        # Perguntar se quer registrar
        confirm = input(f"\nRegistrar '{name}' ({ip})? [y/n] ").lower()
        if confirm != 'y':
            continue
        
        # Se local_key vazia, pedir ao usuário
        if not local_key or local_key == '':
            print(f"  ℹ️  Local key é requerida para controle local")
            local_key = input(f"  Digite a local_key para {name} (ou deixe em branco para pular): ").strip()
            if not local_key:
                print(f"  ⏭️  Pulando {name}")
                continue
        
        # Perguntar device_id simplificado
        simplified_id = input(f"  Device ID simplificado [{dev_id}]: ").strip() or dev_id
        
        # Registrar
        try:
            executor.register_device(
                device_id=simplified_id,
                ip=ip,
                local_key=local_key,
                name=name,
                version=version,
            )
            print(f"  ✅ Registrado: {name}")
            registered_count += 1
        except Exception as e:
            print(f"  ❌ Erro ao registrar: {e}")
    
    print(f"\n✅ {registered_count} devices registrados")
    
    # Step 3: Display Google Assistant setup
    print("\n" + "=" * 70)
    print("🔧 Próximos passos: Configure Google Assistant")
    print("=" * 70)
    print(f"""
Webhook URL: http://<seu-ip>:8503/home/assistant/command

Opções:
1. IFTTT + Google Assistant
   - Create applet: "if This" -> Google Home
   - Set phrase: "ligar ventilador"
   - "Then That" -> Webhooks
   - URL: http://<seu-ip>:8503/home/assistant/command
   - Method: POST
   - Content-Type: application/json
   - Body: {{"text": "ligar ventilador"}}

2. Google Home Routine (local)
   - Open Google Home app
   - Create new routine
   - Trigger: Voice command "ligar ventilador"
   - Action: Send HTTP request to webhook

3. IFTTT Webhook Trigger
   - Set up custom JSON payload
   - Use {{text}} placeholders

Webhook Endpoints:
  GET  /home/assistant/devices      - Listar devices registrados
  POST /home/assistant/command      - Executar comando
  POST /home/assistant/devices/scan - Rescanear rede
  GET  /home/assistant/health       - Health check
""")


def list_devices():
    """Listar devices registrados"""
    executor = get_executor()
    devices = executor.list_devices()
    
    if not devices:
        print("Nenhum device registrado. Execute 'setup' para descobrir.")
        return
    
    print("\n📱 Devices registrados:")
    for dev in devices:
        print(f"\n  {dev['name']}")
        print(f"    ID: {dev['device_id']}")
        print(f"    IP: {dev['ip']}")
        print(f"    Version: {dev['version']}")


def test_command(device_alias: str, action: str):
    """Testar comando em um device"""
    from specialized_agents.home_automation.google_assistant import execute_action
    
    print(f"\n🧪 Testando: {action} {device_alias}")
    result = execute_action(device_alias, action)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Setup Google Assistant + Tinytuya")
    subparsers = parser.add_subparsers(dest="command", help="Comando")
    
    subparsers.add_parser("setup", help="Setup interativo (scan + extract + register)")
    subparsers.add_parser("list", help="Listar devices registrados")
    
    test_parser = subparsers.add_parser("test", help="Testar comando")
    test_parser.add_argument("device", help="Device alias (ex: ventilador)")
    test_parser.add_argument("action", help="Ação (ex: ligar, desligar)")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        scan_and_register()
    elif args.command == "list":
        list_devices()
    elif args.command == "test":
        test_command(args.device, args.action)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
