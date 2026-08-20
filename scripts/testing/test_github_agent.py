#!/usr/bin/env python3
"""
Teste rápido do GitHub Agent
Verifica se todas as conexões estão funcionando
"""

import os

import requests

# Configurações
OLLAMA_HOST = os.getenv("OLLAMA_HOST", os.environ.get('HOMELAB_HOST', 'localhost'))
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "codestral:22b")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

def test_ollama():
    """Testa conexão com Ollama"""
    print("🧪 Testando conexão com Ollama...")
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        models = response.json().get("models", [])
        print(f"   ✅ Ollama conectado! {len(models)} modelos disponíveis:")
        for m in models[:5]:
            print(f"      - {m['name']}")
        if len(models) > 5:
            print(f"      ... e mais {len(models)-5} modelos")
        return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_ollama_generate():
    """Testa geração do Ollama"""
    print(f"\n🧪 Testando geração com modelo {OLLAMA_MODEL}...")
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    data = {
        "model": OLLAMA_MODEL,
        "prompt": "Responda apenas com 'OK': Teste de conexão",
        "stream": False,
        "options": {"num_predict": 10}
    }
    try:
        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()
        result = response.json().get("response", "")
        print(f"   ✅ Modelo respondeu: {result[:50]}")
        return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_github():
    """Testa conexão com GitHub"""
    print("\n🧪 Testando conexão com GitHub API...")
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    
    try:
        # Testa endpoint público
        response = requests.get("https://api.github.com/zen", headers=headers, timeout=10)
        print(f"   ✅ GitHub API acessível: {response.text}")
        
        # Se tem token, testa autenticação
        if GITHUB_TOKEN:
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            if response.status_code == 200:
                user = response.json()
                print(f"   ✅ Autenticado como: {user.get('login')}")
            else:
                print(f"   ⚠️  Token inválido ou expirado (status: {response.status_code})")
        else:
            print("   ⚠️  Sem token - acesso limitado à API pública")
        
        return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_agent_parse():
    """Testa parsing de intenção"""
    print("\n🧪 Testando parsing de intenção...")
    
    from github_agent import GitHubAction, GitHubAgent
    
    agent = GitHubAgent()
    
    test_cases = [
        ("Liste meus repositórios", GitHubAction.LIST_REPOS),
        ("Mostre as issues do microsoft/vscode", GitHubAction.LIST_ISSUES),
        ("Quais são os PRs abertos em facebook/react?", GitHubAction.LIST_PRS),
    ]
    
    for input_text, expected_action in test_cases:
        print(f"\n   Input: '{input_text}'")
        intent = agent.parse_intent(input_text)
        status = "✅" if intent.action == expected_action else "⚠️"
        print(f"   {status} Ação: {intent.action.value} (esperado: {expected_action.value})")
        print(f"      Params: {intent.params}")
        print(f"      Confiança: {intent.confidence:.0%}")


def main():
    print("=" * 60)
    print("🔍 Teste do GitHub Agent")
    print("=" * 60)
    print("\n📋 Configurações:")
    print(f"   OLLAMA_HOST: {OLLAMA_HOST}")
    print(f"   OLLAMA_PORT: {OLLAMA_PORT}")
    print(f"   OLLAMA_MODEL: {OLLAMA_MODEL}")
    print(f"   GITHUB_TOKEN: {'***' if GITHUB_TOKEN else 'não configurado'}")
    print()
    
    ollama_ok = test_ollama()
    
    if ollama_ok:
        test_ollama_generate()
    
    test_github()
    
    if ollama_ok:
        test_agent_parse()
    
    print("\n" + "=" * 60)
    print("✨ Testes concluídos!")
    print("=" * 60)


if __name__ == "__main__":
    main()
