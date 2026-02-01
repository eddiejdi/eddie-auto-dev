#!/usr/bin/env python3
import requests
import json
import re

print("=== TESTE COMPLETO DO GITHUB AGENT ===\n")

# Teste 1: Ollama disponível?
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    print("1. Ollama Status:", "OK" if r.status_code == 200 else "ERRO")
except Exception as e:
    print("1. Ollama ERRO:", e)

# Teste 2: Chat com Ollama (modelo rapido)
print("\n2. Testando chat com qwen2.5-coder:7b...")
try:
    response = requests.post(
        "http://localhost:11434/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [
                {
                    "role": "system",
                    "content": 'Retorne apenas JSON valido no formato: {"action": "list_issues", "params": {"owner": "X", "repo": "Y"}, "confidence": 1.0}',
                },
                {"role": "user", "content": "issues do microsoft/vscode"},
            ],
            "temperature": 0.1,
        },
        timeout=120,
    )
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    print("   Resposta LLM:", content[:200])

    # Tenta parsear JSON
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        intent = json.loads(json_match.group())
        print("   JSON parseado:", intent)
        print("   Owner:", intent.get("params", {}).get("owner", "N/A"))
        print("   Repo:", intent.get("params", {}).get("repo", "N/A"))
except Exception as e:
    print("   Chat ERRO:", e)

# Teste 3: GitHub API
print("\n3. Testando GitHub API...")
try:
    r = requests.get(
        "https://api.github.com/repos/microsoft/vscode/issues?per_page=1", timeout=10
    )
    print("   GitHub API Status:", r.status_code)
    if r.status_code == 200:
        issues = r.json()
        if issues:
            print("   Issue encontrada:", issues[0].get("title", "N/A")[:50])
except Exception as e:
    print("   GitHub ERRO:", e)

print("\n=== FIM DOS TESTES ===")
