#!/usr/bin/env python3
"""
Script de Teste do Ollama - Verifica se o servidor está respondendo
"""

import requests

url = "http://localhost:11434/api/generate"
data = {
    "model": "qwen2.5-coder:1.5b",
    "prompt": "Say hello in Portuguese",
    "stream": False,
    "options": {"num_predict": 50},
}

try:
    print("Testando conexão com Ollama...")
    response = requests.post(url, json=data, timeout=60)
    result = response.json()
    print(f"✅ Resposta: {result.get('response', 'N/A')[:200]}")
except Exception as e:
    print(f"❌ Erro: {e}")
