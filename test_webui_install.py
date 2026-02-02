#!/usr/bin/env python3
"""Teste de conexão e instalação da função no Open WebUI"""

import requests
import sys
import os

WEBUI_URL = "http://192.168.15.2:3000"


def test_connection():
    """Testa conexão com Open WebUI"""
    try:
        r = requests.get(f"{WEBUI_URL}/api/version", timeout=5)
        print(f"✅ Open WebUI v{r.json().get('version')} - ONLINE")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def login(email, password):
    """Faz login e retorna token"""
    r = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=10,
    )
    if r.status_code == 200:
        token = r.json().get("token")
        print(f"✅ Login OK - Token: {token[:20]}...")
        return token
    print(f"❌ Login falhou: {r.status_code} - {r.text}")
    return None


def install_function(token):
    """Instala a função Agent Coordinator"""
    # Ler código
    with open("openwebui_agent_coordinator_function.py", "r") as f:
        code = f.read()

    # Verificar/deletar existente
    r = requests.get(
        f"{WEBUI_URL}/api/v1/functions/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code == 200:
        funcs = r.json()
        print(f"📋 Funções existentes: {len(funcs)}")
        for f in funcs:
            print(f"   - {f.get('id')}: {f.get('name')}")

        # Deletar se existir
        existing = [f for f in funcs if f.get("id") == "agent_coordinator"]
        if existing:
            print("🗑️  Removendo função antiga...")
            requests.delete(
                f"{WEBUI_URL}/api/v1/functions/id/agent_coordinator",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

    # Criar nova
    print("📦 Instalando função...")
    r = requests.post(
        f"{WEBUI_URL}/api/v1/functions/create",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "id": "agent_coordinator",
            "name": "Agent Coordinator",
            "content": code,
            "meta": {"description": "Integra Open WebUI com Agent Coordinator"},
        },
        timeout=30,
    )

    if r.status_code == 200:
        print("✅ Função instalada!")

        # Ativar
        print("🔛 Ativando...")
        r2 = requests.post(
            f"{WEBUI_URL}/api/v1/functions/id/agent_coordinator/toggle",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r2.status_code == 200:
            print("✅ Função ativada!")
            return True
    else:
        print(f"❌ Erro: {r.status_code} - {r.text}")
    return False


def main():
    print("=" * 50)
    print("🔧 INSTALADOR OPEN WEBUI - AGENT COORDINATOR")
    print("=" * 50)

    if not test_connection():
        sys.exit(1)

    # Credenciais via args ou env
    email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEBUI_EMAIL", "")
    password = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get("WEBUI_PASSWORD", "")
    )

    if not email or not password:
        print("\n⚠️  Uso: python test_webui_install.py EMAIL SENHA")
        print("   Ou defina WEBUI_EMAIL e WEBUI_PASSWORD")
        sys.exit(1)

    print(f"\n🔐 Login com: {email}")
    token = login(email, password)
    if not token:
        sys.exit(1)

    if install_function(token):
        print("\n" + "=" * 50)
        print("✅ SUCESSO! Comandos disponíveis:")
        print("   /projeto - Análise de requisitos")
        print("   /codigo  - Gerar código")
        print("   /rag     - Busca RAG")
        print("   /status  - Status do sistema")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
