#!/usr/bin/env python3
"""
Script para instalar função no Open WebUI via API
Requer autenticação - usa variáveis de ambiente ou solicita credenciais
"""

import getpass
import json
import os
import sys

# Tentar usar requests, senão urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.error
    import urllib.request
    HAS_REQUESTS = False

WEBUI_URL = os.getenv("WEBUI_URL", os.environ.get('HOMELAB_URL', 'http://localhost:3000'))
FUNCTION_FILE = "/home/homelab/myClaude/openwebui_agent_coordinator_function.py"

def api_request(method, endpoint, data=None, headers=None):
    """Faz requisição à API"""
    url = f"{WEBUI_URL}{endpoint}"
    
    if HAS_REQUESTS:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            r = requests.post(url, json=data, headers=headers, timeout=30)
        return r.status_code, r.json() if r.text else {}
    else:
        req = urllib.request.Request(url, method=method)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        if data:
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, {}

def login(email, password):
    """Faz login e retorna token"""
    status, resp = api_request("POST", "/api/v1/auths/signin", {
        "email": email,
        "password": password
    })
    if status == 200 and "token" in resp:
        return resp["token"]
    return None

def create_function(token, function_code):
    """Cria função no Open WebUI"""
    # Extrair metadados do código
    import re
    
    title_match = re.search(r'title:\s*(.+)', function_code)
    desc_match = re.search(r'description:\s*(.+)', function_code)
    
    title = title_match.group(1).strip() if title_match else "Agent Coordinator"
    description = desc_match.group(1).strip() if desc_match else "Integração com agentes especializados"
    
    # ID único baseado no título
    func_id = title.lower().replace(" ", "_").replace("-", "_")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Criar função
    data = {
        "id": func_id,
        "name": title,
        "type": "pipe",
        "content": function_code,
        "meta": {
            "description": description
        }
    }
    
    status, resp = api_request("POST", "/api/v1/functions/create", data, headers)
    return status, resp

def list_functions(token):
    """Lista funções existentes"""
    headers = {"Authorization": f"Bearer {token}"}
    status, resp = api_request("GET", "/api/v1/functions", headers=headers)
    return resp if status == 200 else []

def main():
    print("=" * 60)
    print("  Instalador de Funções - Open WebUI")
    print("=" * 60)
    print()
    
    # Verificar se WebUI está acessível
    try:
        status, version = api_request("GET", "/api/version")
        if status == 200:
            print(f"✅ Open WebUI v{version.get('version', '?')} acessível")
        else:
            print(f"❌ Open WebUI não acessível (status: {status})")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        sys.exit(1)
    
    print()
    
    # Credenciais
    email = os.getenv("WEBUI_EMAIL")
    password = os.getenv("WEBUI_PASSWORD")
    
    if not email:
        email = input("Email do admin: ")
    if not password:
        password = getpass.getpass("Senha: ")
    
    # Login
    print("\n🔐 Fazendo login...")
    token = login(email, password)
    
    if not token:
        print("❌ Falha no login. Verifique credenciais.")
        sys.exit(1)
    
    print("✅ Login bem sucedido!")
    
    # Ler arquivo da função
    print(f"\n📄 Lendo função de: {FUNCTION_FILE}")
    try:
        with open(FUNCTION_FILE, 'r') as f:
            function_code = f.read()
        print(f"   {len(function_code)} bytes lidos")
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {FUNCTION_FILE}")
        sys.exit(1)
    
    # Listar funções existentes
    print("\n📋 Funções existentes:")
    functions = list_functions(token)
    if functions:
        for func in functions:
            status_icon = "🟢" if func.get("is_active") else "🔴"
            print(f"   {status_icon} {func.get('name', '?')} ({func.get('id', '?')})")
    else:
        print("   Nenhuma função instalada")
    
    # Criar função
    print("\n🚀 Instalando função 'Agent Coordinator'...")
    status, resp = create_function(token, function_code)
    
    if status in [200, 201]:
        print("✅ Função instalada com sucesso!")
        print(f"   ID: {resp.get('id', '?')}")
        print(f"   Nome: {resp.get('name', '?')}")
    elif status == 409:
        print("⚠️  Função já existe. Atualizando...")
        # TODO: Implementar update
    else:
        print(f"❌ Erro ao instalar função (status: {status})")
        print(f"   Resposta: {resp}")
    
    print("\n" + "=" * 60)
    print("  Instalação concluída!")
    print("=" * 60)

if __name__ == "__main__":
    main()
