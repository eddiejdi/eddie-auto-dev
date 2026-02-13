#!/usr/bin/env python3
"""
Setup simples: criar device_map.json com devices conhecidos.
Sem escanear rede (evita hang).
"""

import json
import sys
from pathlib import Path

# Credenciais Tuya conhecidas
KNOWN_DEVICES = {
    "ventilador_escritorio": {
        "device_id": "ventilador_escritorio",
        "ip": "192.168.15.4",
        "local_key": "0" * 16,  # Placeholder - será preenchido manualmente
        "name": "Ventilador Escritório",
        "version": 3.4,
    },
    "luz_escritorio": {
        "device_id": "luz_escritorio",
        "ip": "192.168.15.5",
        "local_key": "0" * 16,
        "name": "Luz Escritório",
        "version": 3.4,
    },
    "tomada_cozinha": {
        "device_id": "tomada_cozinha",
        "ip": "192.168.15.7",
        "local_key": "0" * 16,
        "name": "Tomada Cozinha",
        "version": 3.4,
    },
    "ar_condicionado": {
        "device_id": "ar_condicionado",
        "ip": "192.168.15.9",
        "local_key": "0" * 16,
        "name": "Ar Condicionado",
        "version": 3.4,
    },
    "tomada_sala": {
        "device_id": "tomada_sala",
        "ip": "192.168.15.16",
        "local_key": "0" * 16,
        "name": "Tomada Sala",
        "version": 3.4,
    },
}


def create_device_map():
    """Criar device_map.json com devices conhecidos"""
    
    device_map_path = Path("agent_data/home_automation/device_map.json")
    device_map_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 70)
    print("📝 Setup Device Map - Google Assistant")
    print("=" * 70)
    print(f"\nCriando: {device_map_path}")
    print(f"\n⚠️  AVISO: Local keys estão como placeholder '0000...'")
    print("  Você precisa obter as chaves reais de:")
    print("    1. Smart Life app (requer extração)")
    print("    2. Arquivo de credenciais Tuya (se tiver)")
    print("    3. Ferramenta tinytuya.wizard()")
    
    # Salvar device_map
    with open(device_map_path, "w") as f:
        json.dump(KNOWN_DEVICES, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Device map criado com {len(KNOWN_DEVICES)} devices\n")
    print("Conteúdo:")
    print(json.dumps(KNOWN_DEVICES, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("📋 Próximas ações:")
    print("=" * 70)
    print("""
1. Obter Local Keys:
   a) Via Smart Life APK (completo)
   b) Via tinytuya.wizard():
      python3 -c "import tinytuya; tinytuya.wizard()"
   
   c) Via Credenciais Cloud:
      - Se tiver access_token Tuya, pode extrair via API
      - Veja: https://github.com/jasonacox/tinytuya

2. Atualizar device_map.json com chaves reais:
   python3 -c "
   import json
   m = json.load(open('agent_data/home_automation/device_map.json'))
   m['ventilador_escritorio']['local_key'] = 'sua_chave_aqui'
   json.dump(m, open('agent_data/home_automation/device_map.json', 'w'), indent=2)
   "

3. Testar controle local:
   curl -X POST http://localhost:8503/home/assistant/command \\
     -H "Content-Type: application/json" \\
     -d '{"text": "ligar ventilador"}'

4. Configurar Google Assistant:
   - IFTTT Webhook
   - Google Routines (local)
   - Google Home app
""")


if __name__ == "__main__":
    create_device_map()
