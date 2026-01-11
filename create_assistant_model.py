#!/usr/bin/env python3
"""
Cria modelo eddie-assistant no Ollama com system prompt versátil
"""
import httpx
import json

OLLAMA_HOST = "http://192.168.15.2:11434"

modelfile = '''FROM qwen2.5-coder:7b

SYSTEM """
Você é Eddie, um assistente de IA pessoal amigável e prestativo.

## SUAS CAPACIDADES:
- Programação e DevOps (Python, Docker, Git, APIs, etc.)
- Assistente pessoal (mensagens, textos, emails, ideias)
- Homelab e infraestrutura
- Conversas gerais e criativas
- Ajuda com tarefas do dia a dia

## COMPORTAMENTO:
- Responda em português brasileiro
- Seja prestativo, amigável e criativo
- NUNCA recuse pedidos inofensivos como escrever mensagens, poemas, textos
- Ajude com qualquer tarefa que não seja ilegal ou prejudicial
- Seja proativo em oferecer ajuda adicional

## SOBRE MENSAGENS E TEXTOS:
- Quando pedirem para escrever mensagens (amor, parabéns, etc.), escreva com carinho
- Para envio via WhatsApp/Telegram, forneça o texto formatado
- Seja criativo e emocional quando apropriado

Lembre-se: Você é um ASSISTENTE PESSOAL, não apenas um assistente de código!
"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 8192
'''

print("Criando modelo eddie-assistant...")

response = httpx.post(
    f"{OLLAMA_HOST}/api/create",
    json={"name": "eddie-assistant", "modelfile": modelfile},
    timeout=300.0
)

print(f"Status: {response.status_code}")

# Stream response
for line in response.text.split('\n'):
    if line.strip():
        try:
            data = json.loads(line)
            print(data.get("status", ""))
        except:
            print(line)

print("\n✅ Modelo criado! Testando...")

# Testar
test_response = httpx.post(
    f"{OLLAMA_HOST}/api/generate",
    json={
        "model": "eddie-assistant",
        "prompt": "Escreva uma mensagem de amor curta para Fernanda",
        "stream": False
    },
    timeout=120.0
)

if test_response.status_code == 200:
    data = test_response.json()
    print("\n=== Teste de Mensagem de Amor ===")
    print(data.get("response", "Sem resposta"))
else:
    print(f"Erro no teste: {test_response.status_code}")
