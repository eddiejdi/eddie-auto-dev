# 🤖 Modelos Eddie - Configuração e Uso

## Modelos Disponíveis

### eddie-assistant (Assistente Pessoal)
- **Base:** dolphin-llama3:8b
- **Propósito:** Assistente pessoal completo sem restrições
- **Uso:** Mensagens pessoais, textos criativos, qualquer solicitação

```bash
# Criar/atualizar modelo
ollama create eddie-assistant -f eddie-assistant-dolphin.Modelfile
```

### eddie-coder (Programação)
- **Base:** qwen2.5-coder:7b
- **Propósito:** Exclusivamente programação e DevOps
- **Restrições:** Recusa pedidos pessoais/não-técnicos

```bash
ollama create eddie-coder -f eddie-coder-strict.Modelfile
```

### eddie-homelab (Infraestrutura)
- **Base:** qwen2.5-coder:7b
- **Propósito:** DevOps, containers, servidores

## Modelfiles

### eddie-assistant-dolphin.Modelfile
```
FROM dolphin-llama3:8b

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER num_ctx 8192

SYSTEM """Você é Eddie, o assistente pessoal de Eduardo.
Você ajuda com QUALQUER coisa que o usuário pedir.
Responda em português brasileiro."""
```

### eddie-coder-strict.Modelfile
```
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
```

## Testando Restrições

```python
import requests

def test_model(model, prompt):
    response = requests.post(
        "http://192.168.15.2:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    return response.json()["response"]

# Teste pessoal (eddie-assistant deve responder, eddie-coder deve recusar)
print(test_model("eddie-assistant", "Escreva uma mensagem de amor"))
print(test_model("eddie-coder", "Escreva uma mensagem de amor"))

# Teste técnico (ambos devem responder)
print(test_model("eddie-coder", "Escreva uma função Python de fatorial"))
```

## Comandos Úteis

```bash
# Listar modelos
ollama list

# Testar modelo
ollama run eddie-assistant "Olá, como vai?"

# Ver informações do modelo
ollama show eddie-assistant

# Remover modelo
ollama rm eddie-assistant
```

---
*Última atualização: 10 de janeiro de 2026*
