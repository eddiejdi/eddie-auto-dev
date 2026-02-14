#!/usr/bin/env python3
"""Testa todas as regioes da Tuya Cloud API para encontrar a correta."""
import tinytuya
import json

API_KEY = "kjg5qhcsgd44uf8ppty8"
API_SECRET = "5a9be7cf8a514ce39112b53045c4b96f"
# Device ID encontrado no scan local
DEVICE_ID = "ebbc9f4aaf16cce3a4wj26"

REGIONS = ["us", "us-e", "eu", "eu-w", "cn", "in", "sg"]

for region in REGIONS:
    print(f"\n--- Region: {region} ---")
    try:
        c = tinytuya.Cloud(
            apiRegion=region,
            apiKey=API_KEY,
            apiSecret=API_SECRET,
            apiDeviceID=DEVICE_ID
        )
        # Tentar obter token
        if hasattr(c, 'token') and c.token:
            print(f"  Token OK: {c.token[:20]}...")
        else:
            print(f"  Token: FALHOU")
            continue
        
        # Tentar listar dispositivos
        devices = c.getdevices(verbose=True)
        if isinstance(devices, dict) and 'Error' in devices:
            print(f"  Error: {devices.get('Error', 'unknown')}")
            # Mostrar detalhes do erro
            print(f"  Details: {json.dumps(devices, indent=2)[:300]}")
        elif isinstance(devices, list):
            print(f"  Dispositivos: {len(devices)}")
            for d in devices[:3]:
                print(f"    - {d.get('name', 'N/A')} (ID: {d.get('id', 'N/A')})")
        else:
            print(f"  Response: {str(devices)[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

print("\n\nDone!")
