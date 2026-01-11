#!/usr/bin/env python3
"""Testa os modelos atualizados"""
import httpx
import json

OLLAMA_HOST = "http://192.168.15.2:11434"

def test_model(model_name: str, prompt: str):
    print(f"\n{'='*50}")
    print(f"Modelo: {model_name}")
    print(f"Prompt: {prompt}")
    print('='*50)
    
    response = httpx.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False
        },
        timeout=120.0
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nResposta:\n{data.get('response', 'Sem resposta')}")
    else:
        print(f"Erro: {response.status_code} - {response.text}")

# Testar ambos modelos
prompt = "Escreva uma mensagem de amor curta e bonita para Fernanda Baldi"

test_model("eddie-assistant", prompt)
test_model("eddie-coder", prompt)

print("\n\n✅ Testes concluídos!")
print("\nAgora você pode usar esses modelos no Open WebUI!")
print("- eddie-assistant: Para tarefas gerais e pessoais")
print("- eddie-coder: Para programação (agora também aceita tarefas pessoais)")
