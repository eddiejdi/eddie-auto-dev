#!/usr/bin/env python3
"""
SmartLife Quick Setup - Configuração Rápida
Conecta à Tuya Cloud e controla dispositivos
"""
import os
import sys
import json
import asyncio
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def setup_tuya_credentials():
    """Configura credenciais da Tuya interativamente."""
    print("=" * 60)
    print("   🏠 SmartLife/Tuya - Configuração Rápida")
    print("=" * 60)
    print()
    print("Para controlar seus dispositivos SmartLife, você precisa")
    print("de credenciais da Tuya IoT Platform.")
    print()
    print("📋 Siga estes passos:")
    print()
    print("1. Acesse: https://iot.tuya.com")
    print("2. Crie uma conta (use o mesmo email do app SmartLife)")
    print("3. Vá em Cloud > Development > Create Cloud Project")
    print("4. Vincule sua conta SmartLife ao projeto")
    print("5. Copie Access ID e Access Secret")
    print()
    
    # Verificar se já tem config
    config_file = Path(__file__).parent / "config" / "config.yaml"
    if config_file.exists():
        print("⚠️  Já existe um config.yaml")
        resp = input("Sobrescrever? (s/N): ").strip().lower()
        if resp != 's':
            print("Mantendo configuração existente.")
            return False
    
    # Coletar credenciais
    print("\n📝 Insira suas credenciais Tuya:\n")
    
    api_key = input("Access ID (API Key): ").strip()
    if not api_key:
        print("❌ Access ID é obrigatório!")
        return False
    
    api_secret = input("Access Secret: ").strip()
    if not api_secret:
        print("❌ Access Secret é obrigatório!")
        return False
    
    print("\n🌍 Selecione sua região:")
    print("  1. Europa (eu)")
    print("  2. América (us)")
    print("  3. China (cn)")
    print("  4. Índia (in)")
    
    region_map = {"1": "eu", "2": "us", "3": "cn", "4": "in"}
    region_choice = input("Região [1]: ").strip() or "1"
    region = region_map.get(region_choice, "eu")
    
    device_id = input("\nDevice ID (qualquer dispositivo, ou Enter para pular): ").strip()
    
    # Criar config.yaml
    config_content = f"""# SmartLife Integration Configuration
# Gerado automaticamente

# Tuya Cloud API
tuya:
  api_key: "{api_key}"
  api_secret: "{api_secret}"
  region: "{region}"
  device_id: "{device_id or 'auto'}"

# Integração Local (TinyTuya)
local:
  enabled: true
  scan_interval: 60
  fallback_to_cloud: true
  devices_file: "config/devices.json"

# Database (SQLite para início)
database:
  type: "sqlite"
  path: "smartlife.db"

# Bot Telegram
telegram:
  enabled: true
  token: "${{TELEGRAM_BOT_TOKEN}}"
  admin_ids:
    - 948686300

# API REST
api:
  host: "0.0.0.0"
  port: 8100
  debug: false

# Logging
logging:
  level: "INFO"
"""
    
    # Salvar
    config_file.parent.mkdir(exist_ok=True)
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"\n✅ Configuração salva em: {config_file}")
    return True


async def test_connection():
    """Testa conexão com a Tuya Cloud."""
    import yaml
    
    config_file = Path(__file__).parent / "config" / "config.yaml"
    if not config_file.exists():
        print("❌ config.yaml não encontrado. Execute setup primeiro.")
        return False
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    tuya_config = config.get("tuya", {})
    
    print("\n🔌 Testando conexão com Tuya Cloud...")
    
    try:
        import tinytuya
        
        cloud = tinytuya.Cloud(
            apiRegion=tuya_config.get("region", "eu"),
            apiKey=tuya_config.get("api_key"),
            apiSecret=tuya_config.get("api_secret"),
            apiDeviceID=tuya_config.get("device_id") if tuya_config.get("device_id") != "auto" else None
        )
        
        # Testar conexão
        result = cloud.getdevices()
        
        if isinstance(result, dict) and "Error" in str(result):
            print(f"❌ Erro: {result}")
            return False
        
        print(f"✅ Conectado! Encontrados {len(result or [])} dispositivos:\n")
        
        devices = result or []
        for i, device in enumerate(devices, 1):
            name = device.get("name", "Unknown")
            dev_id = device.get("id", "")[:12] + "..."
            category = device.get("category", "unknown")
            online = "🟢" if device.get("online", False) else "🔴"
            
            print(f"  {i}. {online} {name}")
            print(f"      ID: {dev_id}")
            print(f"      Tipo: {category}")
            print()
        
        # Salvar dispositivos
        devices_file = Path(__file__).parent / "config" / "devices.json"
        with open(devices_file, 'w') as f:
            json.dump(devices, f, indent=2)
        print(f"💾 Dispositivos salvos em: {devices_file}")
        
        return devices
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def control_device(device_name: str, command: str, value=None):
    """Controla um dispositivo pelo nome."""
    import yaml
    
    config_file = Path(__file__).parent / "config" / "config.yaml"
    devices_file = Path(__file__).parent / "config" / "devices.json"
    
    if not config_file.exists():
        print("❌ Execute setup primeiro!")
        return
    
    if not devices_file.exists():
        print("❌ Execute test primeiro para descobrir dispositivos!")
        return
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    with open(devices_file) as f:
        devices = json.load(f)
    
    # Encontrar dispositivo pelo nome
    device = None
    for d in devices:
        if device_name.lower() in d.get("name", "").lower():
            device = d
            break
    
    if not device:
        print(f"❌ Dispositivo '{device_name}' não encontrado!")
        print("\nDispositivos disponíveis:")
        for d in devices:
            print(f"  - {d.get('name')}")
        return
    
    print(f"\n🎯 Dispositivo: {device.get('name')}")
    print(f"   ID: {device.get('id')}")
    print(f"   Categoria: {device.get('category')}")
    
    # Conectar ao cloud
    import tinytuya
    
    tuya_config = config.get("tuya", {})
    cloud = tinytuya.Cloud(
        apiRegion=tuya_config.get("region", "eu"),
        apiKey=tuya_config.get("api_key"),
        apiSecret=tuya_config.get("api_secret")
    )
    
    device_id = device.get("id")
    
    # Mapear comandos
    print(f"\n⚡ Executando: {command}", f"= {value}" if value else "")
    
    try:
        if command == "on":
            result = cloud.sendcommand(device_id, {"commands": [{"code": "switch", "value": True}]})
        elif command == "off":
            result = cloud.sendcommand(device_id, {"commands": [{"code": "switch", "value": False}]})
        elif command == "speed" or command == "fan_speed":
            # Para ventiladores - speed geralmente vai de 1-100 ou níveis específicos
            result = cloud.sendcommand(device_id, {"commands": [{"code": "fan_speed", "value": int(value)}]})
        elif command == "brightness" or command == "dim":
            result = cloud.sendcommand(device_id, {"commands": [{"code": "bright_value", "value": int(value)}]})
        elif command == "max":
            # Colocar no máximo (ventilador ou brilho)
            category = device.get("category", "")
            if "fan" in category or "ventilador" in device.get("name", "").lower():
                result = cloud.sendcommand(device_id, {"commands": [{"code": "fan_speed", "value": 100}]})
            else:
                result = cloud.sendcommand(device_id, {"commands": [{"code": "bright_value", "value": 100}]})
        elif command == "status":
            result = cloud.getstatus(device_id)
        else:
            # Comando genérico
            result = cloud.sendcommand(device_id, {"commands": [{"code": command, "value": value}]})
        
        print(f"\n📡 Resultado: {json.dumps(result, indent=2)}")
        
        if result and result.get("success", False):
            print("✅ Comando executado com sucesso!")
        else:
            print("⚠️  Verifique o resultado acima")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


async def interactive_menu():
    """Menu interativo."""
    while True:
        print("\n" + "=" * 50)
        print("   🏠 SmartLife Control")
        print("=" * 50)
        print()
        print("  1. Configurar credenciais Tuya")
        print("  2. Testar conexão e listar dispositivos")
        print("  3. Controlar dispositivo")
        print("  4. Ver status de dispositivo")
        print("  0. Sair")
        print()
        
        choice = input("Escolha: ").strip()
        
        if choice == "1":
            setup_tuya_credentials()
        elif choice == "2":
            await test_connection()
        elif choice == "3":
            name = input("Nome do dispositivo: ").strip()
            print("\nComandos: on, off, max, speed <valor>, brightness <valor>")
            cmd_input = input("Comando: ").strip().split()
            if cmd_input:
                cmd = cmd_input[0]
                val = cmd_input[1] if len(cmd_input) > 1 else None
                await control_device(name, cmd, val)
        elif choice == "4":
            name = input("Nome do dispositivo: ").strip()
            await control_device(name, "status")
        elif choice == "0":
            print("👋 Até mais!")
            break
        else:
            print("Opção inválida!")


def main():
    """Ponto de entrada principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SmartLife Quick Control")
    parser.add_argument("--setup", action="store_true", help="Configurar credenciais")
    parser.add_argument("--test", action="store_true", help="Testar conexão")
    parser.add_argument("--device", "-d", help="Nome do dispositivo")
    parser.add_argument("--command", "-c", help="Comando (on/off/max/speed/brightness)")
    parser.add_argument("--value", "-v", help="Valor do comando")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_tuya_credentials()
    elif args.test:
        asyncio.run(test_connection())
    elif args.device and args.command:
        asyncio.run(control_device(args.device, args.command, args.value))
    else:
        # Menu interativo
        asyncio.run(interactive_menu())


if __name__ == "__main__":
    main()
