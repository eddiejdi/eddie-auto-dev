#!/usr/bin/env python3
"""Testa o modelo shared-coder treinado"""
import httpx
import time

print("=" * 50)
print("Testando modelo shared-coder")
print("=" * 50)

start = time.time()

try:
    response = httpx.post(
        "http://192.168.15.2:11434/api/generate",
        json={
            "model": "shared-coder",
            "prompt": "Crie uma função Python para calcular fatorial com recursão",
            "stream": False
        },
        timeout=120.0
    )
    
    if response.status_code == 200:
        data = response.json()
        result = data.get("response", "")
        elapsed = time.time() - start
        
        print(f"\n⏱️ Tempo de resposta: {elapsed:.1f}s")
        print(f"\n📝 Resposta do modelo:\n")
        print("-" * 50)
        print(result[:1500])
        print("-" * 50)
    else:
        print(f"Erro HTTP: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Erro: {e}")
