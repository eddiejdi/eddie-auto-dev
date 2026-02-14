# Configuração: Gemini 2.5 Pro para Home Automation

## Visão Geral

Este projeto usa Gemini 2.5 Pro para interpretação de comandos de linguagem natural (PT-BR) para controle de dispositivos smart home.

## Configuração

### Opção 1: Google AI API (Recomendado para uso pessoal)

1. Obtenha uma API key gratuita em https://ai.google.dev/
2. Adicione ao `.env`:
   ```bash
   GOOGLE_AI_API_KEY=sua-api-key-aqui
   ```

3. Configure o LLM no `specialized_agents/config.py`:
   ```python
   LLM_CONFIG = {
       "provider": "openai_compatible",
       "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
       "model": "gemini-2.0-flash-exp",  # ou gemini-2.5-pro quando disponível
       "api_key_env": "GOOGLE_AI_API_KEY",
       "temperature": 0.3,
       "max_tokens": 8192,
   }
   ```

### Opção 2: Vertex AI (Para produção/empresa)

1. Configure um projeto no Google Cloud
2. Habilite Vertex AI API
3. Configure credenciais:
   ```bash
   gcloud auth application-default login
   ```

4. Configure o LLM:
   ```python
   LLM_CONFIG = {
       "provider": "vertex",
       "project_id": "seu-project-id",
       "location": "us-central1",
       "model": "gemini-2.5-pro",
       "temperature": 0.3,
   }
   ```

### Opção 3: Ollama local (Fallback)

Para usar modelo local sem dependência de API externa:

```python
LLM_CONFIG = {
    "provider": "ollama",
    "base_url": "http://192.168.15.2:11434",
    "model": "qwen2.5-coder:7b",
    "temperature": 0.3,
}
```

## Modelos Recomendados

| Modelo | Uso | Latência | Custo |
|--------|-----|----------|-------|
| gemini-2.0-flash-exp | Testes/desenvolvimento | ~200ms | Grátis |
| gemini-2.5-pro | Produção | ~500ms | Pago |
| qwen2.5-coder:7b (local) | Fallback offline | ~100ms | Hardware local |

## Exemplo de Configuração Completa

```python
# specialized_agents/config.py

import os

LLM_CONFIG = {
    # Provider: "openai_compatible", "vertex", "ollama"
    "provider": "openai_compatible",
    
    # Para Google AI API (Gemini)
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "model": "gemini-2.0-flash-exp",
    "api_key": os.getenv("GOOGLE_AI_API_KEY"),
    
    # Parâmetros de geração
    "temperature": 0.3,  # Baixa para comandos precisos
    "max_tokens": 8192,
    "top_p": 0.9,
    
    # Timeout e retry
    "timeout": 30,  # segundos
    "max_retries": 3,
    
    # Fallback para Ollama local
    "fallback": {
        "provider": "ollama",
        "base_url": "http://192.168.15.2:11434",
        "model": "qwen2.5-coder:7b",
    }
}
```

## Testes

### Teste de configuração

```bash
python3 - << 'EOF'
from specialized_agents.config import LLM_CONFIG
import requests

if LLM_CONFIG["provider"] == "openai_compatible":
    url = f"{LLM_CONFIG['base_url']}chat/completions"
    headers = {"Authorization": f"Bearer {LLM_CONFIG['api_key']}"}
    data = {
        "model": LLM_CONFIG["model"],
        "messages": [{"role": "user", "content": "Olá"}],
        "max_tokens": 50
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(response.json())
EOF
```

### Teste end-to-end

```bash
python3 - << 'EOF'
import asyncio
from specialized_agents.gemini_connector import webhook
from pydantic import BaseModel

class Cmd(BaseModel):
    text: str

async def test():
    commands = [
        "ligar ventilador do escritório",
        "desligar luz da sala",
        "aumentar temperatura do ar condicionado para 22 graus"
    ]
    
    for cmd_text in commands:
        print(f"\n🗣️  Comando: {cmd_text}")
        cmd = Cmd(text=cmd_text)
        result = await webhook(cmd)
        print(f"✓ Resultado: {result['response']['parsed']}")

asyncio.run(test())
EOF
```

## Custos Estimados

### Google AI API (Gemini 2.0 Flash)
- **Grátis** até 1500 requisições/dia
- Após limite: $0.075 por 1M tokens de input

### Google AI API (Gemini 2.5 Pro - quando disponível)
- ~$7.00 por 1M tokens de input
- ~$21.00 por 1M tokens de output

### Vertex AI
- Preços similares, mas com SLA empresarial
- Ver https://cloud.google.com/vertex-ai/pricing

## Troubleshooting

### Erro "API key not valid"
- Verifique se `GOOGLE_AI_API_KEY` está definida
- Regenere a key em https://ai.google.dev/

### Erro "Rate limit exceeded"
- Google AI tem limite de 1500 req/dia gratuitas
- Considere Vertex AI para produção

### Latência alta
- Use `gemini-2.0-flash-exp` em vez de `gemini-2.5-pro`
- Configure cache de respostas
- Use Ollama local para fallback

## Referências

- [Google AI for Developers](https://ai.google.dev/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Vertex AI](https://cloud.google.com/vertex-ai)
