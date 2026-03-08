#!/usr/bin/env python3
"""Script de teste para simular o GitHub Agent"""
import requests
import json
import re

OLLAMA_HOST = "192.168.15.2"
OLLAMA_PORT = "11434"
OLLAMA_MODEL = "github-agent:latest"

SYSTEM_PROMPT = """Você é um assistente de GitHub. Analise o pedido e retorne APENAS JSON válido.

Formato obrigatório:
{"action": "<ação>", "params": {<parâmetros>}, "confidence": <0.0-1.0>}

Ações disponíveis:
- list_issues: owner, repo, state? (ex: microsoft/vscode → owner="microsoft", repo="vscode")

EXEMPLOS IMPORTANTES:
"issues do microsoft/vscode" → {"action": "list_issues", "params": {"owner": "microsoft", "repo": "vscode"}, "confidence": 1.0}

REGRA CRÍTICA: Quando o usuário mencionar "owner/repo", SEMPRE separe em owner e repo distintos nos params.
Responda APENAS com JSON, sem texto adicional."""

def test_parse():
    user_input = "issues do microsoft/vscode"
    
    print(f"=== Entrada: {user_input} ===\n")
    
    # Chama Ollama
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/v1/chat/completions"
    response = requests.post(url, json={
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.1
    }, timeout=120)
    
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    print(f"Resposta LLM:\n{content}\n")
    
    # Parse JSON
    try:
        json_str = content.strip()
        if "```" in json_str:
            json_str = json_str.split("```")[1].replace("json", "").strip()
        
        intent = json.loads(json_str)
        print(f"Intent parseado: {json.dumps(intent, indent=2)}\n")
        
        # Enriquecer se necessário
        p = intent.get("params", {})
        if not p.get("owner") or not p.get("repo") or "/" in p.get("owner", ""):
            repo_pattern = r'([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'
            match = re.search(repo_pattern, user_input)
            if match:
                intent["params"]["owner"] = match.group(1)
                intent["params"]["repo"] = match.group(2)
                print(f"Intent enriquecido: {json.dumps(intent, indent=2)}\n")
        
        owner = intent["params"].get("owner", "")
        repo = intent["params"].get("repo", "")
        
        print(f"Owner final: '{owner}'")
        print(f"Repo final: '{repo}'")
        
        # Testa API GitHub
        if owner and repo:
            print(f"\n=== Testando GitHub API ===")
            gh_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=2"
            print(f"URL: {gh_url}")
            gh_response = requests.get(gh_url, timeout=30)
            print(f"Status: {gh_response.status_code}")
            if gh_response.status_code == 200:
                issues = gh_response.json()
                print(f"Issues encontrados: {len(issues)}")
                if issues:
                    print(f"Primeiro issue: #{issues[0]['number']} - {issues[0]['title'][:50]}...")
            else:
                print(f"Erro: {gh_response.text[:200]}")
        else:
            print("\n❌ Owner ou repo vazios!")
            
    except Exception as e:
        print(f"Erro no parse: {e}")
        # Fallback
        repo_pattern = r'([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'
        match = re.search(repo_pattern, user_input)
        if match:
            print(f"\nFallback - Owner: {match.group(1)}, Repo: {match.group(2)}")

if __name__ == "__main__":
    test_parse()
