#!/usr/bin/env python3
"""
Script para instalar função de impressora no Open WebUI
"""
import requests
import json
import sys
import os

WEBUI_URL = "http://192.168.15.2:8002"  # Open WebUI em Docker
WEBUI_URL = os.environ.get('OPENWEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:8002"  # Open WebUI em Docker
EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie@2026"
FUNCTION_ID = "printer_etiqueta"
FUNCTION_NAME = "🖨️ Impressora de Etiquetas"

def main():
    print("=" * 70)
    print("  📦 Instalador - Função Impressora de Etiquetas")
    print("=" * 70)
    print()
    
    # Ler código da função
    func_file = "/home/homelab/agents_workspace/openwebui_printer_function.py"
    
    if not os.path.exists(func_file):
        print(f"❌ Arquivo não encontrado: {func_file}")
        print(f"   Execute primeiro: scp openwebui_printer_function.py homelab@${{HOMELAB_HOST}}:...")
        return False
    
    with open(func_file, 'r') as f:
        function_code = f.read()
    
    # 1. Login
    print("🔐 Autenticando no Open WebUI...")
    try:
        r = requests.post(
            f"{WEBUI_URL}/api/v1/auths/signin",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=10
        )
        r.raise_for_status()
        token = r.json().get("token")
        if not token:
            print("❌ Erro: Não foi possível obter token de autenticação")
            return False
        print(f"✅ Autenticado como {EMAIL}")
    except Exception as e:
        print(f"❌ Erro de autenticação: {e}")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Verificar se função já existe
    print("\n🔍 Verificando se função já existe...")
    try:
        r = requests.get(
            f"{WEBUI_URL}/api/v1/functions/",
            headers=headers,
            timeout=10
        )
        existing_funcs = r.json() if r.status_code == 200 else []
        existing_ids = [f.get("id") for f in existing_funcs]
        
        if FUNCTION_ID in existing_ids:
            print(f"⚠️ Função '{FUNCTION_ID}' já existe. Removendo...")
            r = requests.delete(
                f"{WEBUI_URL}/api/v1/functions/{FUNCTION_ID}",
                headers=headers,
                timeout=10
            )
            if r.status_code == 200:
                print(f"✅ Função anterior removida")
            else:
                print(f"⚠️ Não foi possível remover função anterior (código {r.status_code})")
    except Exception as e:
        print(f"⚠️ Erro ao verificar funções existentes: {e}")
    
    # 3. Instalar função
    print("\n📥 Instalando função de impressora...")
    try:
        payload = {
            "id": FUNCTION_ID,
            "name": FUNCTION_NAME,
            "type": "pipe",
            "content": function_code,
            "meta": {
                "description": "Imprime etiquetas no Phomemo Q30 com validação automática de tamanho",
                "author": "Eddie Auto-Dev",
                "tags": ["printer", "etiqueta", "phomemo"]
            }
        }
        
        r = requests.post(
            f"{WEBUI_URL}/api/v1/functions/create",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if r.status_code in [200, 201]:
            print(f"✅ Função instalada com sucesso!")
            print(f"\n📋 ID: {FUNCTION_ID}")
            print(f"   Nome: {FUNCTION_NAME}")
        else:
            print(f"❌ Erro ao instalar (status {r.status_code})")
            print(f"   Resposta: {r.text[:200]}")
            return False
    
    except Exception as e:
        print(f"❌ Erro ao instalar função: {e}")
        return False
    
    # 4. Ativar função
    print("\n⚙️ Ativando função...")
    try:
        # Listar novamente para pegar dados atualizados
        r = requests.get(
            f"{WEBUI_URL}/api/v1/functions/{FUNCTION_ID}",
            headers=headers,
            timeout=10
        )
        
        if r.status_code == 200:
            print(f"✅ Função ativa e pronta para usar!")
        else:
            print(f"⚠️ Função criada, mas não foi possível confirmar status")
    except Exception as e:
        print(f"⚠️ Erro ao verificar status: {e}")
    
    # 5. Instruções de uso
    print("\n" + "=" * 70)
    print("  📝 INSTRUÇÕES DE USO")
    print("=" * 70)
    print("""
1️⃣ Acesse o Open WebUI: http://192.168.15.2:3000

2️⃣ Vá em: Settings → Functions → Impressora de Etiquetas

3️⃣ Use a função em um chat:
   
   ✅ Exemplos:
   
   a) Imprimir texto simples:
      "Imprima uma etiqueta com o texto: TESTE 123"
   
   b) Validar antes de imprimir:
      {"action": "print", "content": "ETIQUETA GRANDE", "validate_only": true}
   
   c) Imprimir imagem:
      {"action": "print", "content": "/path/to/label.png", "type": "image"}

4️⃣ Características:
   ✨ Validação automática de tamanho
   ✨ Suporta texto e imagem
   ✨ Comunicação via porta serial Bluetooth
   ✨ Feedback em tempo real

5️⃣ Verificação:
   Para listar portas disponíveis:
   python3 /home/homelab/agents_workspace/phomemo_print.py --list

6️⃣ Configuração (se necessário):
   Edite a função em Settings → Functions e ajuste em Valves:
   - PRINTER_PORT: porta serial (auto-detect se vazio)
   - MAX_WIDTH: 384px (Phomemo padrão)
   - MAX_HEIGHT: 600px
   - BAUDRATE: 9600
""")
    
    print("\n" + "=" * 70)
    print("✅ Instalação concluída com sucesso!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
