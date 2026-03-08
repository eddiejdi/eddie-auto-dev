# 🤖 Modelos Shared - Configuração e Uso

## Modelos Disponíveis

### shared-assistant (Assistente Pessoal)
- **Base:** dolphin-llama3:8b
- **Propósito:** Assistente pessoal completo sem restrições
- **Uso:** Mensagens pessoais, textos criativos, qualquer solicitação

```bash
# Criar/atualizar modelo
ollama create shared-assistant -f shared-assistant-dolphin.Modelfile
### shared-coder (Programação)
- **Base:** qwen2.5-coder:7b
- **Propósito:** Exclusivamente programação e DevOps
- **Restrições:** Recusa pedidos pessoais/não-técnicos

```bash
ollama create shared-coder -f shared-coder-strict.Modelfile
### shared-homelab (Infraestrutura)
- **Base:** qwen2.5-coder:7b
- **Propósito:** DevOps, containers, servidores

## Modelfiles

### shared-assistant-dolphin.Modelfile
FROM dolphin-llama3:8b

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER num_ctx 8192

SYSTEM """Você é Shared, o assistente pessoal de Eduardo.
Você ajuda com QUALQUER coisa que o usuário pedir.
Responda em português brasileiro."""
### shared-coder-strict.Modelfile
FROM qwen2.5-coder:7b

PARAMETER temperature 0.3
PARAMETER num_ctx 8192

SYSTEM """Você é um assistente de programação.
REGRA ABSOLUTA: Você SÓ responde sobre:
- Código e programação
- DevOps e infraestrutura
- Tecnologia

Para QUALQUER outro assunto, responda APENAS:
"Desculpe, sou um assistente especializado em programação."
"""
## Testando Restrições

import requests

def test_model(model, prompt):
    response = requests.post(
        "http://192.168.15.2:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    return response.json()["response"]

# Teste pessoal (shared-assistant deve responder, shared-coder deve recusar)
print(test_model("shared-assistant", "Escreva uma mensagem de amor"))
print(test_model("shared-coder", "Escreva uma mensagem de amor"))

# Teste técnico (ambos devem responder)
print(test_model("shared-coder", "Escreva uma função Python de fatorial"))
## Comandos Úteis

```bash
# Listar modelos
ollama list

# Testar modelo
ollama run shared-assistant "Olá, como vai?"

# Ver informações do modelo
ollama show shared-assistant

# Remover modelo
ollama rm shared-assistant
---
*Última atualização: 10 de janeiro de 2026*
