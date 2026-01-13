#!/usr/bin/env python3
"""
Tenta todas as regiões do TinyTuya para descobrir onde está a conta.
"""
import tinytuya

API_KEY = "kjg5qhcsgd44uf8ppty8"
API_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"

# Todas as regiões disponíveis
REGIONS = ['us', 'us-e', 'eu', 'eu-w', 'in', 'cn']

print("=" * 60)
print("   🌐 Testando Todas as Regiões TinyTuya")
print("=" * 60)
print()

for region in REGIONS:
    print(f"🔍 Testando região: {region}...", end=" ")
    
    try:
        c = tinytuya.Cloud(
            apiRegion=region,
            apiKey=API_KEY,
            apiSecret=API_SECRET
        )
        
        devices = c.getdevices()
        
        if isinstance(devices, list) and len(devices) > 0:
            print(f"✅ ENCONTRADOS {len(devices)} DISPOSITIVOS!")
            print()
            print(f"🎉 Sua conta está na região: {region}")
            print()
            for d in devices:
                print(f"   📱 {d.get('name', 'Unknown')}")
                print(f"      ID: {d.get('id')}")
                print(f"      Key: {d.get('key', 'N/A')}")
                print()
            break
        elif isinstance(devices, dict) and devices.get('Error'):
            print(f"❌ {devices.get('Error', 'Erro')[:40]}")
        else:
            print(f"⚠️ Vazio")
    except Exception as e:
        print(f"❌ Erro: {str(e)[:40]}")

else:
    print()
    print("=" * 60)
    print("❌ Nenhum dispositivo encontrado em nenhuma região.")
    print()
    print("Isso significa que a conta SmartLife NÃO está vinculada")
    print("ao projeto no Tuya Developer Platform.")
    print()
    print("Para vincular:")
    print("1. Acesse platform.tuya.com")
    print("2. Vá em Cloud > Development > seu projeto")
    print("3. Aba 'Devices' > 'Link App Account'")
    print("4. Clique 'Add App Account' > 'Tuya App Account Authorization'")
    print("5. Escaneie o QR Code com o app SmartLife")
    print("   (App > Eu > ícone de Scan no topo)")
