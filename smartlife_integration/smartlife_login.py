#!/usr/bin/env python3
"""
SmartLife Login - Obtém credenciais usando conta SmartLife
Alternativa quando iot.tuya.com não está disponível
"""

import sys
import json
import hashlib
import requests
from pathlib import Path

# APIs SmartLife por região
SMARTLIFE_APIS = {
    "eu": "https://px1.tuyaeu.com",
    "us": "https://px1.tuyaus.com",
    "cn": "https://px1.tuyacn.com",
    "in": "https://px1.tuyain.com",
}

# Client IDs do app SmartLife
CLIENT_IDS = {"smartlife": "ekmnwp9f5pnh3trdtpgy", "tuyasmart": "3fjrekuxank9eaej3gcx"}


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def get_token_smartlife(username, password, region="eu", app="smartlife"):
    """
    Obtém token de acesso usando credenciais do SmartLife App.
    """
    base_url = SMARTLIFE_APIS.get(region, SMARTLIFE_APIS["eu"])
    client_id = CLIENT_IDS.get(app, CLIENT_IDS["smartlife"])

    # Preparar login
    password_hash = md5(password)

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Tentar login
    login_url = f"{base_url}/homeassistant/auth.do"

    data = {
        "userName": username,
        "password": password_hash,
        "countryCode": "55",  # Brasil
        "bizType": app,
        "from": "tuya",
    }

    try:
        response = requests.post(login_url, data=data, headers=headers)
        result = response.json()

        if result.get("access_token"):
            return {
                "success": True,
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_in": result.get("expires_in"),
                "region": region,
            }
        else:
            return {
                "success": False,
                "error": result.get("errorMsg", "Login failed"),
                "code": result.get("responseStatus"),
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_devices_smartlife(access_token, region="eu"):
    """
    Lista dispositivos usando token SmartLife.
    """
    base_url = SMARTLIFE_APIS.get(region, SMARTLIFE_APIS["eu"])

    headers = {"Content-Type": "application/json"}

    # Obter dispositivos
    url = f"{base_url}/homeassistant/skill"

    data = {
        "header": {"name": "Discovery", "namespace": "discovery", "payloadVersion": 1},
        "payload": {"accessToken": access_token},
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        result = response.json()

        if "payload" in result and "devices" in result["payload"]:
            return {"success": True, "devices": result["payload"]["devices"]}
        else:
            return {"success": False, "error": "No devices found", "response": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def control_device_smartlife(access_token, device_id, command, value=None, region="eu"):
    """
    Controla dispositivo usando token SmartLife.
    """
    base_url = SMARTLIFE_APIS.get(region, SMARTLIFE_APIS["eu"])

    url = f"{base_url}/homeassistant/skill"

    # Mapear comandos para formato SmartLife
    if command == "on":
        directive = {"name": "turnOnOff", "value": "1"}
    elif command == "off":
        directive = {"name": "turnOnOff", "value": "0"}
    elif command == "max":
        directive = {"name": "windSpeedSet", "value": "4"}  # Máximo geralmente é 4
    elif command == "speed":
        speed_map = {
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "low": "1",
            "medium": "2",
            "high": "3",
            "max": "4",
        }
        directive = {"name": "windSpeedSet", "value": speed_map.get(str(value), "4")}
    elif command == "brightness":
        directive = {"name": "brightnessSet", "value": str(value)}
    else:
        directive = {"name": command, "value": str(value) if value else "1"}

    data = {
        "header": {
            "name": directive["name"],
            "namespace": "control",
            "payloadVersion": 1,
        },
        "payload": {
            "accessToken": access_token,
            "devId": device_id,
            "value": directive["value"],
        },
    }

    try:
        response = requests.post(url, json=data)
        result = response.json()

        return {
            "success": result.get("header", {}).get("code") == "SUCCESS",
            "response": result,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def interactive_setup():
    """Setup interativo usando credenciais SmartLife."""
    print("=" * 60)
    print("   🏠 SmartLife - Login Direto")
    print("=" * 60)
    print()
    print("Use suas credenciais do APP SmartLife (não precisa de iot.tuya.com)")
    print()

    # Coletar credenciais
    username = input("📧 Email/Telefone do SmartLife: ").strip()
    password = input("🔑 Senha do SmartLife: ").strip()

    print("\n🌍 Região:")
    print("  1. Europa (eu)")
    print("  2. América (us)")
    print("  3. China (cn)")

    region_choice = input("Escolha [1]: ").strip() or "1"
    region = {"1": "eu", "2": "us", "3": "cn"}.get(region_choice, "eu")

    print(f"\n🔐 Fazendo login na região {region}...")

    result = get_token_smartlife(username, password, region)

    if result["success"]:
        print("✅ Login bem-sucedido!")

        # Salvar token
        token_file = Path(__file__).parent / "config" / "smartlife_token.json"
        token_file.parent.mkdir(exist_ok=True)

        with open(token_file, "w") as f:
            json.dump(
                {
                    "access_token": result["access_token"],
                    "refresh_token": result.get("refresh_token"),
                    "region": region,
                    "username": username,
                },
                f,
                indent=2,
            )

        print(f"💾 Token salvo em: {token_file}")

        # Listar dispositivos
        print("\n📱 Buscando dispositivos...")
        devices_result = get_devices_smartlife(result["access_token"], region)

        if devices_result["success"]:
            devices = devices_result["devices"]
            print(f"\n✅ Encontrados {len(devices)} dispositivos:\n")

            for i, device in enumerate(devices, 1):
                name = device.get("name", "Unknown")
                dev_id = device.get("id", "")
                dev_type = device.get("dev_type", "unknown")
                online = "🟢" if device.get("online", False) else "🔴"

                print(f"  {i}. {online} {name}")
                print(f"      ID: {dev_id}")
                print(f"      Tipo: {dev_type}")
                print()

            # Salvar dispositivos
            devices_file = Path(__file__).parent / "config" / "devices.json"
            with open(devices_file, "w") as f:
                json.dump(devices, f, indent=2)

            print(f"💾 Dispositivos salvos em: {devices_file}")
            return devices
        else:
            print(f"⚠️  Erro ao buscar dispositivos: {devices_result.get('error')}")
    else:
        print(f"❌ Erro no login: {result.get('error')}")

    return None


def control_interactive():
    """Controle interativo de dispositivos."""
    token_file = Path(__file__).parent / "config" / "smartlife_token.json"
    devices_file = Path(__file__).parent / "config" / "devices.json"

    if not token_file.exists():
        print("❌ Token não encontrado. Execute o login primeiro!")
        return

    with open(token_file) as f:
        token_data = json.load(f)

    if not devices_file.exists():
        print("❌ Lista de dispositivos não encontrada!")
        return

    with open(devices_file) as f:
        devices = json.load(f)

    print("\n📱 Dispositivos disponíveis:\n")
    for i, device in enumerate(devices, 1):
        name = device.get("name", "Unknown")
        print(f"  {i}. {name}")

    choice = input("\nEscolha o número do dispositivo: ").strip()

    try:
        device = devices[int(choice) - 1]
    except:
        print("❌ Escolha inválida!")
        return

    print(f"\n🎯 Dispositivo: {device.get('name')}")
    print("\nComandos: on, off, max, speed <1-4>")

    cmd_input = input("Comando: ").strip().split()
    if not cmd_input:
        return

    command = cmd_input[0]
    value = cmd_input[1] if len(cmd_input) > 1 else None

    print(f"\n⚡ Executando: {command}" + (f" = {value}" if value else ""))

    result = control_device_smartlife(
        token_data["access_token"], device["id"], command, value, token_data["region"]
    )

    if result["success"]:
        print("✅ Comando executado com sucesso!")
    else:
        print(f"❌ Erro: {result.get('error', result.get('response'))}")


def main():
    """Menu principal."""
    while True:
        print("\n" + "=" * 50)
        print("   🏠 SmartLife Direct Control")
        print("=" * 50)
        print()
        print("  1. Login com conta SmartLife")
        print("  2. Listar dispositivos")
        print("  3. Controlar dispositivo")
        print("  4. Ventilador escritório MAX")
        print("  0. Sair")
        print()

        choice = input("Escolha: ").strip()

        if choice == "1":
            interactive_setup()
        elif choice == "2":
            token_file = Path(__file__).parent / "config" / "smartlife_token.json"
            if token_file.exists():
                with open(token_file) as f:
                    token = json.load(f)
                result = get_devices_smartlife(token["access_token"], token["region"])
                if result["success"]:
                    for d in result["devices"]:
                        print(f"  - {d.get('name')}: {d.get('id')}")
            else:
                print("❌ Faça login primeiro!")
        elif choice == "3":
            control_interactive()
        elif choice == "4":
            # Atalho para ventilador escritório
            token_file = Path(__file__).parent / "config" / "smartlife_token.json"
            devices_file = Path(__file__).parent / "config" / "devices.json"

            if token_file.exists() and devices_file.exists():
                with open(token_file) as f:
                    token = json.load(f)
                with open(devices_file) as f:
                    devices = json.load(f)

                # Procurar ventilador do escritório
                fan = None
                for d in devices:
                    name = d.get("name", "").lower()
                    if "ventilador" in name and "escrit" in name:
                        fan = d
                        break
                    elif "fan" in name and ("office" in name or "escrit" in name):
                        fan = d
                        break

                if fan:
                    print(f"\n🌀 Aumentando {fan.get('name')} ao máximo...")
                    result = control_device_smartlife(
                        token["access_token"], fan["id"], "max", region=token["region"]
                    )
                    if result["success"]:
                        print("✅ Ventilador no máximo!")
                    else:
                        print(f"❌ Erro: {result}")
                else:
                    print("❌ Ventilador do escritório não encontrado!")
                    print("Dispositivos disponíveis:")
                    for d in devices:
                        print(f"  - {d.get('name')}")
            else:
                print("❌ Faça login primeiro (opção 1)")
        elif choice == "0":
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "login":
            interactive_setup()
        elif sys.argv[1] == "devices":
            token_file = Path(__file__).parent / "config" / "smartlife_token.json"
            if token_file.exists():
                with open(token_file) as f:
                    token = json.load(f)
                result = get_devices_smartlife(token["access_token"], token["region"])
                print(json.dumps(result, indent=2))
        elif sys.argv[1] == "fan-max":
            # Comando direto para ventilador no máximo
            main()  # Vai para menu, use opção 4
    else:
        main()
