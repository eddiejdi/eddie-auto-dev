# Integração de Modelo OpenAI Compatible no Copilot

## Configuração Realizada

Foi adicionado suporte para o modelo OpenAI compatible `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` ao Copilot/Continue.dev.

## Arquivos Criados

### `.continue/config.json` (Continue.dev via OpenRouter)
Configuração para uso com OpenRouter, um agregador de modelos LLM com API compatível com OpenAI.

**Modelo adicionado:**
- Provider: `openrouter`
- Model: `sk-or-v1-...` (token completo)
- Base URL: `https://openrouter.ai/api/v1`
- Context Length: 200.000 tokens

### `.continue/config-scaleway.json` (Alternativa - Scaleway AI)
Configuração alternativa usando endpoint OpenAI-compatible genérico (ex: Scaleway AI).

**Uso:**
Se estiver usando Scaleway AI ou outro provedor OpenAI-compatible:
```bash
# Copiar config alternativa
cp .continue/config-scaleway.json .continue/config.json
```

## Como Usar

### 1. No VS Code com Continue.dev

O Continue.dev carrega automaticamente o arquivo `.continue/config.json` da workspace. O modelo estará disponível no seletor de modelos dentro do Chat do Continue.

**Passos:**
1. Abrir VS Code
2. Abrir palete de comandos: `Ctrl+Shift+P`
3. Digitar "Continue: Open Models"
4. Selecionar "OpenAI Compatible - sk-or model"

### 2. Configuração Global do Continue

Se preferir usar globalmente, copie o arquivo para o diretório home:
```bash
mkdir -p ~/.continue
cp .continue/config.json ~/.continue/config.json
```

### 3. Via CLI (Subagent)

O modelo também pode ser usado via API especializada de agentes:
```python
from specialized_agents.config import LLM_CONFIG

# Configurar fallback para modelo OpenAI-compatible
config = {
    "provider": "openai_compatible",
    "base_url": "https://api.scaleway.ai/v1",
    "api_key": "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",
    "model": "gpt-4",
    "temperature": 0.3,
    "max_tokens": 8192,
}
```

## Fluxo de Roteamento de Modelos

**Hierarquia do Copilot:**
1. **GPU0 (Ollama local)** - `http://192.168.15.2:11434` - qwen2.5-coder:7b (PADRÃO)
2. **GPU1 (Ollama GPU1)** - `http://192.168.15.2:11435` - qwen3:0.6b (leve)
3. **OpenAI Compatible** - sk-or-v1 (via OpenRouter ou Scaleway) - FALLBACK

## Segurança & Secrets

⚠️ **IMPORTANTE**: O arquivo `.continue/config.json` contém a chave API. **NÃO COMMITTAR** com secrets!

Para manter seguro:
```bash
# 1. Adicionar ao .gitignore
echo ".continue/config.json" >> .gitignore

# 2. Usar variáveis de ambiente
export CONTINUE_API_KEY="sk-or-v1-..."
export CONTINUE_API_BASE="https://api.scaleway.ai/v1"

# 3. Ou usar vault do projeto
python3 tools/vault/secret_store.py --set OPENAI_COMPATIBLE_API_KEY "sk-or-v1-..."
```

## Teste da Configuração

### Via cURL (testar endpoint)
```bash
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer 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" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "olá"}],
    "temperature": 0.3,
    "max_tokens": 100
  }'
```

### Via Continue.dev
1. Abrir Chat do Continue (`Ctrl+L`)
2. Digitar uma pergunta simples
3. Verificar se a resposta vem do modelo OpenAI-compatible

## Troubleshooting

### ❌ Erro: "Model not found"
- Verificar se a API key está correta
- Confirmar que a URL base está acessível
- Testar com cURL antes

### ❌ Erro: "Unauthorized"
- Revisar se o token `sk-or-...` está correto no arquivo
- Confirmar que a API key ainda é válida

### ❌ Erro: "Connection refused"
- Verificar conectividade com a URL base
- Se usando `https://`, confirmar certificados SSL

## Próximos Passos

1. **Validar funcionamento**: Abrir VS Code e testar modelo no Chat
2. **Adicionar aos testes**: `tests/test_continue_integration.py`
3. **Documentar no wiki**: Adicionar página no Wiki.js sobre modelos disponíveis
4. **CI/CD**: Validar modelo disponível em pipeline antes de merge

## Referências

- [Continue.dev Documentation](https://docs.continue.dev)
- [OpenRouter Models](https://openrouter.ai)
- [GitHub Copilot Instructions](./.github/copilot-instructions.md)
