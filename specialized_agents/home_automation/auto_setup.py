#!/usr/bin/env python3
"""
Script de teste: Descobre devices Tuya na rede e cria device_map inicial.
Sem interação, apenas automático.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from specialized_agents.home_automation.tinytuya_executor import get_executor


def auto_setup():
    """Descobrir devices e criar configuração básica"""
    print("\n" + "=" * 70)
    print("🔍 Descrobindo Devices Tuya na rede...")
    print("=" * 70)
    
    executor = get_executor()
    
    # Scan
    print("\n[1/3] Scanning...")
    devices = executor.scan_network(force_refresh=True)
    
    if not devices:
        print("❌ Nenhum device encontrado na rede.")
        print("\nCertifique-se que:")
        print("  1. Devices estão conectados à mesma Wi-Fi (192.168.15.x)")
        print("  2. Devices foram pareados com Smart Life")
        print("  3. Tinytuya consegue fazer broadcast em sua rede")
        return
    
    print(f"✅ {len(devices)} devices descobertos\n")
    
    # Listar
    print("[2/3] Devices descobertos:")
    for idx, (dev_id, info) in enumerate(devices.items(), 1):
        print(f"\n  [{idx}] {info.get('device_name', 'Unknown')}")
        print(f"      ID: {dev_id}")
        print(f"      IP: {info.get('ip')}")
        print(f"      Key: {info.get('local_key', 'N/A')}")
        print(f"      Version: {info.get('protocol_version', 3.4)}")
    
    # Auto-registrar com nomes padrão (usuário pode editar depois)
    print("\n[3/3] Auto-registrando devices...")
    
    # Mapeamento automático baseado em IP/keywords
    device_name_mapping = {
        "192.168.15.4": "ventilador_escritorio",
        "192.168.15.5": "luz_escritorio",
        "192.168.15.7": "tomada_cozinha",
        "192.168.15.9": "ar_condicionado",
        "192.168.15.16": "tomada_sala",
    }
    
    registered = []
    for dev_id, info in devices.items():
        ip = info.get('ip')
        name = info.get('device_name', f'Device_{ip}')
        local_key = info.get('local_key', '')
        version = info.get('protocol_version', 3.4)
        
        # Se temos local key, registrar
        if local_key and len(local_key) > 10:
            # Usar nome simplificado do mapeamento ou nome original
            simple_id = device_name_mapping.get(ip, dev_id)
            
            executor.register_device(
                device_id=simple_id,
                ip=ip,
                local_key=local_key,
                name=name,
                version=version,
            )
            registered.append((simple_id, name, ip))
            print(f"  ✅ {name} ({simple_id})")
        else:
            print(f"  ⚠️  {name} - sem local_key, precisa ser registrado manualmente")
    
    print(f"\n✅ {len(registered)} devices registrados\n")
    
    # Mostrar device_map
    print("=" * 70)
    print("📄 Device Map (agent_data/home_automation/device_map.json):")
    print("=" * 70)
    
    with open("agent_data/home_automation/device_map.json", "r") as f:
        device_map = json.load(f)
        print(json.dumps(device_map, indent=2, ensure_ascii=False))
    
    # Próximos passos
    print("\n" + "=" * 70)
    print("✨ Próximos passos:")
    print("=" * 70)
    print("""
1. Teste local (terminal):
   python3 specialized_agents/home_automation/setup_google_assistant.py test ventilador ligar

2. Configure Google Assistant:
   - IFTTT: Create applet with webhook
   - Google Routines: Set webhook URL (requer IP público/ngrok)

3. Teste via webhook:
   curl -X POST http://localhost:8503/home/assistant/command \\
     -H "Content-Type: application/json" \\
     -d '{"text": "ligar ventilador"}'

4. Diga no seu telefone:
   "OK Google, ligar ventilador"
""")


if __name__ == "__main__":
    auto_setup()
