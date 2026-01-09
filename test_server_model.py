#!/usr/bin/env python3
"""Testa o modelo eddie-coder no servidor local"""
import requests
import time

print("=" * 50)
print("Testando modelo eddie-coder")
print("=" * 50)

start = time.time()

try:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "eddie-coder",
            "prompt": "Oi, quem e voce?",
            "stream": False
        },
        timeout=180
    )
    
    if response.status_code == 200:
        data = response.json()
        result = data.get("response", "")
        elapsed = time.time() - start
        
        print(f"\nTempo: {elapsed:.1f}s")
        print(f"\nResposta:\n{result[:800]}")
    else:
        print(f"Erro: {response.status_code}")
except Exception as e:
    print(f"Erro: {e}")
