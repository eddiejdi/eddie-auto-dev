#!/usr/bin/env python3
"""
Instalador de Função no Open WebUI
Uso: python install_webui_function.py <email> <senha>
"""
import requests
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Uso: python install_webui_function.py <email> <senha>")
        print("Exemplo: python install_webui_function.py admin@exemplo.com 123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    base_url = "http://192.168.15.2:3000"
    
    print(f"🔐 Fazendo login como: {email}")
    
    # 1. Login
    try:
        r = requests.post(
            f"{base_url}/api/v1/auths/signin",
            json={"email": email, "password": password},
            timeout=10
        )
        if r.status_code != 200:
            print(f"❌ Erro no login: {r.status_code} - {r.text}")
            sys.exit(1)
        
        token = r.json().get("token")
        print(f"✅ Login OK! Token obtido.")
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        sys.exit(1)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Ler código da função
    function_file = os.path.join(os.path.dirname(__file__), "openwebui_agent_coordinator_function.py")
    with open(function_file, "r") as f:
        function_code = f.read()
    
    print(f"📦 Função carregada: {len(function_code)} bytes")
    
    # 3. Verificar se função já existe
    r = requests.get(f"{base_url}/api/v1/functions/", headers=headers)
    existing = r.json() if r.status_code == 200 else []
    
    function_id = "agent_coordinator"
    function_exists = any(f.get("id") == function_id for f in existing)
    
    # 4. Criar ou atualizar função
    function_data = {
        "id": function_id,
        "name": "Agent Coordinator",
        "content": function_code,
        "meta": {
            "description": "Integra Open WebUI com Agent Coordinator - Análise de requisitos, geração de código, RAG"
        }
    }
    
    if function_exists:
        print("🔄 Atualizando função existente...")
        r = requests.post(
            f"{base_url}/api/v1/functions/id/{function_id}/update",
            headers=headers,
            json=function_data
        )
    else:
        print("➕ Criando nova função...")
        r = requests.post(
            f"{base_url}/api/v1/functions/create",
            headers=headers,
            json=function_data
        )
    
    if r.status_code in [200, 201]:
        print("✅ Função instalada com sucesso!")
        
        # 5. Ativar a função
        print("🔌 Ativando função...")
        r = requests.post(
            f"{base_url}/api/v1/functions/id/{function_id}/toggle",
            headers=headers
        )
        if r.status_code == 200:
            print("✅ Função ativada!")
        
        print("\n" + "=" * 50)
        print("🎉 INSTALAÇÃO COMPLETA!")
        print("=" * 50)
        print("\nComandos disponíveis no chat:")
        print("  /projeto <descrição> - Inicia análise de requisitos")
        print("  /codigo <linguagem> <descrição> - Gera código")
        print("  /rag <pergunta> - Busca no RAG")
        print("  /status - Status do sistema")
        print("\nAcesse: http://192.168.15.2:3000")
    else:
        print(f"❌ Erro ao instalar: {r.status_code} - {r.text}")

if __name__ == "__main__":
    main()
