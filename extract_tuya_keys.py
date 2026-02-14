#!/usr/bin/env python3
"""
Extração automatizada de local_keys da Tuya Cloud API
Usa credenciais do usuário para obter dispositivos e chaves
"""
import json
import sys
import tinytuya

# Credenciais Tuya Cloud (via env vars)
TUYA_EMAIL = os.environ.get("TUYA_EMAIL", "edenilson.adm@gmail.com")
TUYA_PASSWORD = os.environ["TUYA_PASSWORD"]  # Required env var

print("🔑 Extraindo local_keys da Tuya Cloud...")
print("=" * 60)

try:
    # Executar o wizard programaticamente
    # O tinytuya.wizard() aceita inputs interativos, mas vamos usar a API diretamente
    
    # Primeiro, tentar obter as credenciais já salvas
    import os
    tuya_json_path = os.path.expanduser("~/.tinytuya.json")
    
    config = {}
    if os.path.exists(tuya_json_path):
        with open(tuya_json_path) as f:
            config = json.load(f)
            print(f"✓ Configuração existente carregada de {tuya_json_path}")
    
    # Se não tiver API Key/Secret, precisamos executar o wizard manualmente
    if not config.get("apiKey") or not config.get("apiSecret"):
        print("\n⚠️  API Key/Secret não encontrados em ~/.tinytuya.json")
        print("Executando wizard interativo do tinytuya...")
        print("\nQuando solicitado:")
        print(f"  Email: {TUYA_EMAIL}")
        print(f"  Password: {TUYA_PASSWORD}")
        print("  Region: us (Eastern America)")
        print("\nIniciando wizard...\n")
        
        # Executar wizard (será interativo)
        tinytuya.wizard()
        
        # Recarregar config após wizard
        if os.path.exists(tuya_json_path):
            with open(tuya_json_path) as f:
                config = json.load(f)
    
    # Agora fazer scan da rede local para pegar os devices
    print("\n📡 Fazendo scan da rede local...")
    devices = tinytuya.deviceScan(verbose=False, maxretry=5)
    
    print(f"\n✓ Encontrados {len(devices)} dispositivos:")
    print("=" * 60)
    
    # Salvar devices em formato JSON
    output = {}
    for ip, dev_info in devices.items():
        device_id = dev_info.get('id', 'unknown')
        local_key = dev_info.get('key', '')
        version = dev_info.get('version', '3.3')
        
        output[device_id] = {
            'ip': ip,
            'id': device_id,
            'key': local_key,
            'version': version,
            'name': dev_info.get('name', 'Unknown')
        }
        
        print(f"\nDispositivo: {dev_info.get('name', 'Unknown')}")
        print(f"  IP: {ip}")
        print(f"  ID: {device_id}")
        print(f"  Key: {local_key if local_key else '(vazio - precisa wizard)'}")
        print(f"  Version: {version}")
    
    # Salvar no arquivo de saída
    output_file = "tuya_devices_with_keys.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Dispositivos salvos em {output_file}")
    print("\n" + "=" * 60)
    
    # Estatísticas
    devices_with_keys = sum(1 for d in output.values() if d['key'])
    devices_without_keys = len(output) - devices_with_keys
    
    print(f"\nEstatísticas:")
    print(f"  Total de dispositivos: {len(output)}")
    print(f"  Com local_key: {devices_with_keys}")
    print(f"  Sem local_key: {devices_without_keys}")
    
    if devices_without_keys > 0:
        print("\n⚠️  Alguns dispositivos não têm local_key.")
        print("   Isso pode ocorrer se:")
        print("   1. O wizard não foi executado com sucesso")
        print("   2. Os dispositivos não estão configurados na mesma conta Tuya")
        print("   3. A conta não tem permissão Cloud Development")
    
    sys.exit(0 if devices_with_keys > 0 else 1)
    
except Exception as e:
    print(f"\n❌ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
