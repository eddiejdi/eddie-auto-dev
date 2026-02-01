#!/usr/bin/env python3
"""
SmartLife/Tuya Control via Home Assistant API
Usa a integração local do Home Assistant para controlar dispositivos
"""

import sys
import json
from pathlib import Path

try:
    import tinytuya
except ImportError:
    print("Instalando tinytuya...")
    import subprocess

    subprocess.run([sys.executable, "-m", "pip", "install", "tinytuya", "-q"])
    import tinytuya


def scan_devices():
    """Escaneia rede local em busca de dispositivos Tuya."""
    print("\n🔍 Escaneando rede local por dispositivos Tuya...")
    print("   (Isso pode levar até 30 segundos)\n")

    devices = tinytuya.deviceScan(verbose=True, maxretry=3)

    if devices:
        print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")

        device_list = []
        for ip, info in devices.items():
            dev_id = info.get("gwId", info.get("id", "unknown"))
            version = info.get("version", "3.3")

            device_data = {
                "ip": ip,
                "id": dev_id,
                "version": version,
                "name": f"Device_{dev_id[:8]}",  # Nome placeholder
                "key": "",  # Precisa ser obtido
            }
            device_list.append(device_data)

            print(f"  📱 IP: {ip}")
            print(f"     ID: {dev_id}")
            print(f"     Versão: {version}")
            print()

        # Salvar
        devices_file = Path(__file__).parent / "config" / "devices_scan.json"
        devices_file.parent.mkdir(exist_ok=True)
        with open(devices_file, "w") as f:
            json.dump(device_list, f, indent=2)

        print(f"💾 Salvo em: {devices_file}")
        return device_list
    else:
        print("❌ Nenhum dispositivo encontrado na rede local")
        print("\nPossíveis causas:")
        print("  - Dispositivos não estão na mesma rede/subnet")
        print("  - Firewall bloqueando portas 6666/6667/7000")
        print("  - Dispositivos em modo cloud-only")
        return []


def control_local_device(ip, device_id, local_key, command, value=None, version="3.3"):
    """
    Controla dispositivo Tuya via conexão local (LAN).

    Requer: IP, Device ID e Local Key do dispositivo.
    """
    print(f"\n🔌 Conectando ao dispositivo {ip}...")

    try:
        # Determinar tipo de dispositivo
        # BulbDevice para lâmpadas, OutletDevice para tomadas
        device = tinytuya.Device(device_id, ip, local_key)
        device.set_version(float(version))

        # Obter status atual
        status = device.status()
        print(f"📊 Status atual: {json.dumps(status, indent=2)}")

        if command == "on":
            result = device.turn_on()
        elif command == "off":
            result = device.turn_off()
        elif command == "status":
            return status
        elif command == "toggle":
            # Verificar estado atual e inverter
            if status.get("dps", {}).get("1", False):
                result = device.turn_off()
            else:
                result = device.turn_on()
        elif command == "speed" or command == "fan_speed":
            # Para ventiladores - DPS geralmente é 3 ou 4 para velocidade
            result = device.set_value(3, int(value))  # Tenta DPS 3
            if not result:
                result = device.set_value(4, int(value))  # Tenta DPS 4
        elif command == "max":
            # Velocidade máxima (geralmente 4 ou 100 dependendo do dispositivo)
            result = device.set_value(3, 4)  # Tenta nível 4
        elif command == "brightness" or command == "dim":
            result = device.set_value(2, int(value))  # DPS 2 geralmente é brilho
        else:
            # Comando genérico - tenta como DPS
            try:
                dps = int(command)
                result = device.set_value(dps, value if value else True)
            except ValueError:
                result = {"error": f"Comando desconhecido: {command}"}

        print(f"📡 Resultado: {result}")
        return result

    except Exception as e:
        print(f"❌ Erro: {e}")
        return {"error": str(e)}


def get_local_key_instructions():
    """Mostra instruções para obter Local Key."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          Como Obter a LOCAL KEY dos Dispositivos                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  OPÇÃO 1: Via Tuya IoT Platform (Recomendado)                   ║
║  ─────────────────────────────────────────────                  ║
║  1. Acesse: https://auth.tuya.com                               ║
║  2. Faça login (crie conta se necessário)                       ║
║  3. Vá em Cloud > Development > Create Project                  ║
║  4. Link Tuya App Account (escaneie QR com SmartLife)           ║
║  5. Em Devices, encontre seu dispositivo                        ║
║  6. A Local Key está nos detalhes do dispositivo                ║
║                                                                  ║
║  OPÇÃO 2: Via TinyTuya Wizard                                   ║
║  ──────────────────────────────                                 ║
║  Execute: python -m tinytuya wizard                             ║
║  Informe suas credenciais da Tuya IoT quando solicitado         ║
║                                                                  ║
║  OPÇÃO 3: Via Home Assistant                                    ║
║  ─────────────────────────────                                  ║
║  Se você usa Home Assistant com integração LocalTuya,           ║
║  as Local Keys estão em .storage/core.config_entries            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def setup_device_manually():
    """Configura um dispositivo manualmente."""
    print("\n📝 Configuração Manual de Dispositivo\n")

    name = input("Nome do dispositivo (ex: Ventilador Escritório): ").strip()
    ip = input("IP do dispositivo (ex: 192.168.1.100): ").strip()
    device_id = input("Device ID (do scan ou app): ").strip()
    local_key = input("Local Key (16 caracteres): ").strip()
    version = input("Versão do protocolo [3.3]: ").strip() or "3.3"

    device = {
        "name": name,
        "ip": ip,
        "id": device_id,
        "key": local_key,
        "version": version,
    }

    # Carregar dispositivos existentes ou criar novo
    devices_file = Path(__file__).parent / "config" / "devices_local.json"
    devices_file.parent.mkdir(exist_ok=True)

    devices = []
    if devices_file.exists():
        with open(devices_file) as f:
            devices = json.load(f)

    # Adicionar ou atualizar
    found = False
    for i, d in enumerate(devices):
        if d.get("id") == device_id:
            devices[i] = device
            found = True
            break

    if not found:
        devices.append(device)

    with open(devices_file, "w") as f:
        json.dump(devices, f, indent=2)

    print(f"\n✅ Dispositivo salvo em: {devices_file}")
    return device


def control_saved_device(device_name, command, value=None):
    """Controla um dispositivo salvo pelo nome."""
    devices_file = Path(__file__).parent / "config" / "devices_local.json"

    if not devices_file.exists():
        print("❌ Nenhum dispositivo configurado!")
        print("   Use a opção de setup manual primeiro.")
        return

    with open(devices_file) as f:
        devices = json.load(f)

    # Buscar dispositivo
    device = None
    for d in devices:
        if device_name.lower() in d.get("name", "").lower():
            device = d
            break

    if not device:
        print(f"❌ Dispositivo '{device_name}' não encontrado!")
        print("\nDispositivos configurados:")
        for d in devices:
            print(f"  - {d.get('name')}")
        return

    if not device.get("key"):
        print(f"❌ Local Key não configurada para {device.get('name')}!")
        get_local_key_instructions()
        return

    return control_local_device(
        device["ip"],
        device["id"],
        device["key"],
        command,
        value,
        device.get("version", "3.3"),
    )


def main():
    """Menu principal."""
    while True:
        print("\n" + "=" * 55)
        print("   🏠 SmartLife/Tuya - Controle Local")
        print("=" * 55)
        print()
        print("  1. Escanear dispositivos na rede")
        print("  2. Como obter Local Key")
        print("  3. Configurar dispositivo manualmente")
        print("  4. Controlar dispositivo salvo")
        print("  5. Teste rápido de dispositivo")
        print("  0. Sair")
        print()

        choice = input("Escolha: ").strip()

        if choice == "1":
            scan_devices()
        elif choice == "2":
            get_local_key_instructions()
        elif choice == "3":
            setup_device_manually()
        elif choice == "4":
            name = input("Nome do dispositivo: ").strip()
            print("\nComandos: on, off, toggle, max, speed <1-4>, status")
            cmd_input = input("Comando: ").strip().split()
            if cmd_input:
                cmd = cmd_input[0]
                val = cmd_input[1] if len(cmd_input) > 1 else None
                control_saved_device(name, cmd, val)
        elif choice == "5":
            print("\n🧪 Teste rápido de dispositivo")
            ip = input("IP: ").strip()
            dev_id = input("Device ID: ").strip()
            local_key = input("Local Key: ").strip()
            print("\nComando: on, off, status")
            cmd = input("Comando: ").strip()
            control_local_device(ip, dev_id, local_key, cmd)
        elif choice == "0":
            print("👋 Até mais!")
            break


if __name__ == "__main__":
    main()
