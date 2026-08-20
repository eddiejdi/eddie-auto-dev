#!/usr/bin/env python3
"""
Instala a função Agent Coordinator no Open WebUI automaticamente.
Uso: python install_function_webui.py <email> <senha>
"""

import os
import re
import sys
from pathlib import Path

import requests

HOST = os.environ.get('HOMELAB_HOST', 'localhost')
WEBUI_URL = os.environ.get('WEBUI_URL', f"http://{HOST}:3000")
FUNCTION_FILE = Path(__file__).parent / "openwebui_agent_coordinator_function.py"

def main():
    if len(sys.argv) < 3:
        print("Uso: python install_function_webui.py <email> <senha>")
        print("\nOu acesse manualmente:")
        print(f"  1. Abra {WEBUI_URL}")
        print("  2. Faça login como admin")
        print("  3. Vá em Settings → Functions")
        print("  4. Clique em '+ Add Function' ou 'Import'")
        print(f"  5. Cole o conteúdo de: {FUNCTION_FILE}")
        print("  6. Ative a função")
        print("  7. Associe a um modelo (ex: qwen2.5-coder:7b)")
        return 1
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"🔐 Fazendo login em {WEBUI_URL}...")
    
    # Login
    try:
        r = requests.post(f"{WEBUI_URL}/api/v1/auths/signin", json={
            "email": email,
            "password": password
        }, timeout=30)
        
        if r.status_code != 200:
            print(f"❌ Erro no login: {r.status_code}")
            print(r.text)
            return 1
        
        token = r.json().get("token")
        if not token:
            print("❌ Token não retornado")
            return 1
        
        print("✅ Login OK!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return 1
    
    # Ler código da função
    if not FUNCTION_FILE.exists():
        print(f"❌ Arquivo não encontrado: {FUNCTION_FILE}")
        return 1
    
    function_code = FUNCTION_FILE.read_text()
    
    # Extrair metadados
    title_match = re.search(r'title:\s*(.+)', function_code)
    desc_match = re.search(r'description:\s*(.+)', function_code)
    
    title = title_match.group(1).strip() if title_match else "Agent Coordinator"
    description = desc_match.group(1).strip() if desc_match else "Integração com agentes"
    func_id = "agent_coordinator"
    
    print(f"📦 Instalando função: {title}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Verificar se já existe
    r = requests.get(f"{WEBUI_URL}/api/v1/functions", headers=headers)
    existing = r.json() if r.status_code == 200 else []
    
    exists = any(f.get("id") == func_id for f in existing)
    
    if exists:
        print("⚠️ Função já existe. Atualizando...")
        r = requests.post(f"{WEBUI_URL}/api/v1/functions/update", json={
            "id": func_id,
            "name": title,
            "type": "pipe",
            "content": function_code,
            "meta": {"description": description}
        }, headers=headers)
    else:
        print("➕ Criando nova função...")
        r = requests.post(f"{WEBUI_URL}/api/v1/functions/create", json={
            "id": func_id,
            "name": title,
            "type": "pipe",
            "content": function_code,
            "meta": {"description": description}
        }, headers=headers)
    
    if r.status_code in [200, 201]:
        print("✅ Função instalada com sucesso!")
        print()
        print("📋 Próximos passos:")
        print(f"  1. Acesse {WEBUI_URL}")
        print("  2. Vá em Settings → Functions")
        print("  3. Ative a função 'Agent Coordinator'")
        print("  4. Associe a um modelo (qwen2.5-coder:7b)")
        print()
        print("🎯 Comandos disponíveis após ativação:")
        print("  /projeto <descrição> - Inicia análise de requisitos")
        print("  /codigo <linguagem> <descrição> - Gera código")
        print("  /rag <pergunta> - Busca no RAG")
        print("  /status - Status do sistema")
        return 0
    else:
        print(f"❌ Erro ao criar função: {r.status_code}")
        print(r.text)
        return 1

if __name__ == "__main__":
    sys.exit(main())
