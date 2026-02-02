#!/usr/bin/env python3
"""
Teste usando TinyTuya Cloud API (método oficial).
"""

import tinytuya

# Suas credenciais
ACCESS_ID = "xgkk3vwjnpasrp34hpwf"
ACCESS_SECRET = "d0b4f1d738a141cbaf45eeffa6363820"

# Testar diferentes regiões
regions = ["us", "eu", "cn"]

print("🔑 Testando conexão com TinyTuya Cloud...")
print(f"   Access ID: {ACCESS_ID[:10]}...")
print()

for region in regions:
    print(f"📡 Testando região: {region}")

    try:
        cloud = tinytuya.Cloud(
            apiRegion=region, apiKey=ACCESS_ID, apiSecret=ACCESS_SECRET
        )

        # Testar conexão
        devices = cloud.getdevices()

        if devices and not isinstance(devices, str):
            print(f"   ✅ SUCESSO! Encontrados {len(devices)} dispositivos")
            for dev in devices[:5]:
                status = "🟢" if dev.get("online") else "🔴"
                print(
                    f"      {status} {dev.get('name', '?')} - {dev.get('id', '?')[:16]}..."
                )
            break
        else:
            print(f"   ❌ Falhou ou sem dispositivos: {devices}")

    except Exception as e:
        print(f"   ❌ Erro: {e}")

    print()

print()
print("=" * 60)
print()
print("Se todas as regiões falharam, verifique:")
print()
print("1. Acesse https://auth.tuya.com e faça login")
print("2. Vá em Cloud > Development")
print("3. Verifique se o projeto existe")
print("4. Na aba 'Service API', certifique-se que estas APIs estão autorizadas:")
print("   - IoT Core")
print("   - Smart Home Basic Service")
print("   - Device Status Notification")
print("5. Na aba 'Devices', vincule sua conta SmartLife:")
print("   - Clique em 'Link Tuya App Account'")
print("   - Escaneie o QR code com o app SmartLife")
print()
print("IMPORTANTE: A região do teste deve ser a mesma do Data Center")
print("onde você criou o projeto!")
