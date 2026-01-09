# Guia de Configuração do Twinny para Ollama Remoto

## Seu Servidor Ollama
- **Host:** 192.168.15.2
- **Porta:** 11434
- **Modelos disponíveis:**
  - `codestral:22b` (22.2B parâmetros)
  - `deepseek-coder-v2:16b` (15.7B parâmetros)
  - `qwen2.5-coder:7b` (7.6B parâmetros)
  - `qwen2.5-coder:1.5b` (1.5B parâmetros)

---

## Configuração via Interface do Twinny

### 1. Abrir Providers do Twinny
1. Clique no ícone do Twinny na barra lateral esquerda (🤖)
2. No painel do Twinny, clique no ícone de engrenagem ⚙️
3. Navegue até a seção "Providers"

### 2. Configurar Provider para Chat

Crie ou edite um provider com estas configurações:

| Campo | Valor |
|-------|-------|
| **Label** | `Ollama Homelab Chat` |
| **Provider** | `ollama` |
| **Type** | `chat` |
| **Hostname** | `192.168.15.2` |
| **Port** | `11434` |
| **Path** | `/v1/chat/completions` |
| **Model** | `codestral:22b` (ou outro modelo) |
| **Protocol** | `http` |

### 3. Configurar Provider para Code Completion (FIM)

Crie outro provider para auto-complete:

| Campo | Valor |
|-------|-------|
| **Label** | `Ollama Homelab FIM` |
| **Provider** | `ollama` |
| **Type** | `fim` (Fill-in-Middle) |
| **Hostname** | `192.168.15.2` |
| **Port** | `11434` |
| **Path** | `/api/generate` |
| **Model** | `codestral:22b` |
| **Protocol** | `http` |
| **FIM Template** | `codestral` ou `deepseek` |

---

## Configuração via settings.json

Adicione estas configurações no seu `settings.json` (Ctrl+Shift+P → "Preferences: Open User Settings (JSON)"):

```json
{
    "twinny.chatModelName": "codestral:22b",
    "twinny.fimModelName": "codestral:22b",
    "twinny.apiHostname": "192.168.15.2",
    "twinny.apiPort": 11434,
    "twinny.apiProtocol": "http",
    "twinny.apiPath": "/v1/chat/completions",
    "twinny.fimApiPath": "/api/generate",
    "twinny.apiProvider": "ollama",
    "twinny.enabled": true,
    "twinny.enabledChat": true,
    "twinny.enabledCodeActions": true,
    "twinny.autoSuggestEnabled": true
}
```

---

## Testar a Conexão

### Via Terminal (teste rápido):
```bash
# Testar endpoint de chat
curl http://192.168.15.2:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codestral:22b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Testar endpoint de generate
curl http://192.168.15.2:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codestral:22b",
    "prompt": "def hello():"
  }'
```

---

## Modelos Recomendados por Uso

| Uso | Modelo Recomendado | Por que |
|-----|-------------------|---------|
| **Chat (qualidade)** | `codestral:22b` | Maior, mais preciso |
| **Chat (velocidade)** | `qwen2.5-coder:7b` | Bom equilíbrio |
| **FIM/Auto-complete** | `qwen2.5-coder:1.5b` | Rápido para sugestões em tempo real |
| **Deep Coding** | `deepseek-coder-v2:16b` | Especializado em código |

---

## Troubleshooting

### "Connection error"
1. Verifique se Ollama está rodando: `curl http://192.168.15.2:11434/api/tags`
2. Verifique firewall do servidor
3. Certifique-se que Ollama está configurado para aceitar conexões externas (`OLLAMA_HOST=0.0.0.0`)

### Modelo não responde
1. Verifique se o modelo está baixado: `ollama list` no servidor
2. Tente com modelo menor primeiro (`qwen2.5-coder:1.5b`)

### Lento
1. Use modelos menores para FIM/auto-complete
2. Ajuste timeout nas configurações do twinny
