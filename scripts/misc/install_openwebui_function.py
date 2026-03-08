#!/usr/bin/env python3
"""
Instalador de Função para Open WebUI
Instala a função Agent Coordinator automaticamente
"""

import requests
import json
import sys
import getpass

WEBUI_URL = "http://192.168.15.2:3000"

def login(email: str, password: str) -> str:
    """Faz login e retorna o token JWT"""
    resp = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=10
    )
    if resp.status_code != 200:
        print(f"❌ Erro no login: {resp.status_code} - {resp.text}")
        sys.exit(1)
    data = resp.json()
    return data.get("token")

def get_functions(token: str) -> list:
    """Lista funções existentes"""
    resp = requests.get(
        f"{WEBUI_URL}/api/v1/functions/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json()
    return []

def create_function(token: str, function_id: str, name: str, content: str) -> bool:
    """Cria uma nova função"""
    payload = {
        "id": function_id,
        "name": name,
        "content": content,
        "meta": {
            "description": "Integra Open WebUI com Agent Coordinator"
        }
    }
    resp = requests.post(
        f"{WEBUI_URL}/api/v1/functions/create",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30
    )
    if resp.status_code == 200:
        return True
    print(f"Erro ao criar: {resp.status_code} - {resp.text}")
    return False

def toggle_function(token: str, function_id: str) -> bool:
    """Ativa a função"""
    resp = requests.post(
        f"{WEBUI_URL}/api/v1/functions/id/{function_id}/toggle",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    return resp.status_code == 200

def main():
    print("="*60)
    print("🔧 INSTALADOR DE FUNÇÃO - OPEN WEBUI")
    print("="*60)
    print()
    
    # Credenciais
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        email = input("📧 Email: ")
        password = getpass.getpass("🔑 Senha: ")
    
    print()
    print("🔐 Fazendo login...")
    token = login(email, password)
    print("✅ Login OK")
    
    # Ler código da função
    print("📄 Carregando função...")
    with open("openwebui_agent_coordinator_function.py", "r") as f:
        function_code = f.read()
    
    function_id = "agent_coordinator"
    function_name = "Agent Coordinator"
    
    # Verificar se já existe
    print("🔍 Verificando funções existentes...")
    functions = get_functions(token)
    existing = [f for f in functions if f.get("id") == function_id]
    
    if existing:
        print(f"⚠️  Função '{function_id}' já existe!")
        print("   Deletando para reinstalar...")
        requests.delete(
            f"{WEBUI_URL}/api/v1/functions/id/{function_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
    
    # Criar função
    print("📦 Instalando função...")
    if create_function(token, function_id, function_name, function_code):
        print("✅ Função criada com sucesso!")
    else:
        print("❌ Falha ao criar função")
        sys.exit(1)
    
    # Ativar
    print("🔛 Ativando função...")
    if toggle_function(token, function_id):
        print("✅ Função ativada!")
    
    print()
    print("="*60)
    print("✅ INSTALAÇÃO CONCLUÍDA!")
    print("="*60)
    print()
    print("📋 Comandos disponíveis no chat:")
    print("   /projeto <desc>  - Inicia análise de requisitos")
    print("   /codigo <lang>   - Gera código")
    print("   /rag <pergunta>  - Busca no RAG")
    print("   /status          - Status do sistema")
    print()
    print("💡 Dica: Associe a função a um modelo em Settings → Models")

if __name__ == "__main__":
    main()
