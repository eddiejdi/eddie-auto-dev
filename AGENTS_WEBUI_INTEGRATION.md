# 🤖 Agentes Especializados no WebUI

Integração completa dos agentes especializados do seu servidor com **Open WebUI**, permitindo usar todos os agentes (Python, JavaScript, Go, Rust, Java, C#, PHP, TypeScript) e agentes especializados (BPM, Confluence, Security, Data, Performance) como modelos disponíveis no WebUI.

## 📋 O que foi adicionado

### 1. **Ponte de Integração** (`agents_webui_bridge.py`)
- Detecta automaticamente agentes locais e remotos (homelab)
- Expõe agentes como modelos compatíveis com OpenWebUI/Ollama
- Roteia requisições para o agente apropriado

### 2. **Endpoints OpenWebUI-Compatíveis** (em `api.py`)
```
GET  /v1/models                          # Lista modelos (compatível Ollama)
POST /v1/chat/completions                # Chat via agentes
GET  /api/models                         # Alias para /v1/models
POST /api/chat/completions               # Alias para /v1/chat/completions
GET  /agents/models                      # Detalhes dos agentes como modelos
```

### 3. **Modelos de Agentes** (em `openwebui_integration.py`)
Adicionados 8 novos perfis:
- `python_agent`: Agente Python via API
- `javascript_agent`: Agente JavaScript via API  
- `typescript_agent`: Agente TypeScript via API
- `go_agent`: Agente Go via API
- `rust_agent`: Agente Rust via API
- `java_agent`: Agente Java via API
- `csharp_agent`: Agente C# via API
- `php_agent`: Agente PHP via API

### 4. **Configuração** (`site/agents-config.json`)
Arquivo que centraliza configuração de todos os agentes com:
- Ícones, cores, descrições
- Capacidades de cada agente
- URLs de API e endpoints
- Informações de integração

### 5. **Script de Registro** (`register_agents_webui.py`)
Registra agentes automaticamente no Open WebUI como modelos disponíveis.

## 🚀 Como usar

### Opção A: Usar agentes via API diretamente

**1. Listar agentes disponíveis:**
```bash
curl http://localhost:8503/v1/models | jq
```

**2. Chamar um agente (compatível Ollama/OpenWebUI):**
```bash
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent-python",
    "messages": [
      {"role": "user", "content": "Crie um REST API simples com FastAPI"}
    ],
    "temperature": 0.7
  }'
```

**Modelos disponíveis:**
- `agent-python` - Python Expert
- `agent-javascript` - JavaScript Expert
- `agent-typescript` - TypeScript Expert
- `agent-go` - Go Expert
- `agent-rust` - Rust Expert
- `agent-java` - Java Expert
- `agent-csharp` - C# Expert
- `agent-php` - PHP Expert
- `homelab-*` - Agentes remotos no homelab (se disponível)

### Opção B: Usar via Open WebUI

**1. Registrar agentes no WebUI:**
```bash
python3 register_agents_webui.py \
  --webui-url http://192.168.15.2:3000 \
  --api-url http://localhost:8503
```

**2. Acessar WebUI:**
- Abra http://192.168.15.2:3000
- Vá para **Modelos > Modelos Disponíveis**
- Procure por agentes (agent-python, homelab-go, etc)
- Selecione um agente
- Comece a conversar!

**3. Ou usar via perfis de modelo (já configurados):**
```bash
# No telegram_bot.py ou openwebui_integration.py
IntegrationClient().set_profile("python_agent")
```

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# URLs padrão
API_HOST=http://localhost:8503           # Local API
HOMELAB_HOST=192.168.15.2                # Homelab IP
HOMELAB_API=http://192.168.15.2:8503     # Homelab API
OPENWEBUI_HOST=http://192.168.15.2:3000  # Open WebUI
```

### Arquivo de Configuração

Editar `site/agents-config.json` para:
- Personalizar descrições dos agentes
- Adicionar novas capacidades
- Mudar cores dos ícones
- Configurar endpoints customizados

## 📊 Exemplos de Uso

### 1. Python Agent - Gerar FastAPI
```bash
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent-python",
    "messages": [
      {
        "role": "user",
        "content": "Crie um REST API com autenticação JWT"
      }
    ],
    "temperature": 0.3
  }' | jq '.choices[0].message.content'
```

### 2. Go Agent - CLI Tool
```bash
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent-go",
    "messages": [
      {
        "role": "user",
        "content": "Crie uma CLI para listar arquivos recursivamente"
      }
    ]
  }' | jq '.choices[0].message.content'
```

### 3. Rust Agent - WebAssembly
```bash
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent-rust",
    "messages": [
      {
        "role": "user",
        "content": "Crie um módulo WASM para processar imagens"
      }
    ]
  }'
```

### 4. TypeScript + React
```bash
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent-typescript",
    "messages": [
      {
        "role": "user",
        "content": "Crie um componente React com TypeScript para um dashboard de métricas"
      }
    ]
  }'
```

## 🌐 Agentes Remotos (Homelab)

Se o homelab estiver disponível em `192.168.15.2:8503`:

```bash
# Listar agentes remotos
curl http://localhost:8503/v1/models | jq '.models[] | select(.model | startswith("homelab"))'

# Usar agente remoto
curl -X POST http://localhost:8503/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "homelab-python",
    "messages": [{"role": "user", "content": "Describe your capabilities"}]
  }'
```

## 📡 Integração com Múltiplas Plataformas

### OpenWebUI
- Conectar à API em `http://localhost:8503`
- Listar modelos: `GET /v1/models`
- Chat: `POST /v1/chat/completions`

### LLaMA.cpp ou Ollama
- Usar `http://localhost:8503` como host Ollama compatibility
- Funciona como drop-in replacement

### LangChain / LlamaIndex
```python
from langchain.llms import Ollama

llm = Ollama(
    base_url="http://localhost:8503",
    model="agent-python",
    temperature=0.7
)
response = llm("Crie um algoritmo de busca binária")
```

### VSCode Copilot / IDE
- Configure como servidor customizado em `http://localhost:8503`
- Selecione modelo `agent-typescript` ou `agent-python`

## 🔍 Diagnóstico

### Verificar conectividade
```bash
# API está rodando?
curl http://localhost:8503/health

# Agentes disponíveis?
curl http://localhost:8503/agents

# Modelos OpenWebUI?
curl http://localhost:8503/v1/models

# Homelab acessível?
curl http://192.168.15.2:8503/health
```

### Logs
```bash
# API local
journalctl -u specialized-agents-api -f

# Homelab
ssh homelab@192.168.15.2 journalctl -u specialized-agents-api -f
```

### Script de debug
```bash
python3 register_agents_webui.py --list-agents
python3 register_agents_webui.py --list-webui-models
python3 register_agents_webui.py --examples
```

## 🎯 Roadmap

- [ ] Suporte a streaming de respostas
- [ ] Cache de respostas para agentes frequentes
- [ ] Autenticação e autorização por agente
- [ ] Rate limiting por modelo
- [ ] Metrics e tracing de chamadas
- [ ] UI customizada no WebUI para agentes
- [ ] Webhooks para integração externa

## 📚 Arquivos Modificados/Criados

```
✅ specialized_agents/agents_webui_bridge.py    - Nova ponte de integração
✅ specialized_agents/api.py                    - +Endpoints OpenWebUI
✅ openwebui_integration.py                     - +Perfis de agentes
✅ site/agents-config.json                      - Nova configuração
✅ register_agents_webui.py                     - Novo script de registro
```

## 🆘 Troubleshooting

### "Agents Bridge not available"
- Verificar se `agents_webui_bridge.py` está no PATH
- Reiniciar API: `systemctl restart specialized-agents-api`

### Agentes não aparecem no WebUI
- Executar: `python3 register_agents_webui.py`
- Verificar logs: `docker logs open-webui`
- Limpar cache: `docker exec open-webui rm -rf /app/backend/cache`

### Erro ao chamar agente
- Verificar se agente está ativo: `curl http://localhost:8503/agents`
- Observar logs da API: `journalctl -u specialized-agents-api -f`

### Homelab não responde
- SSH disponível? `ssh homelab@192.168.15.2`
- API rodando? `curl http://192.168.15.2:8503/health`
- Network? `ping 192.168.15.2`

## 📧 Support

Para issues ou sugestões:
- GitHub: https://github.com/eddiejdi/eddie-auto-dev
- Issues: Abra um issue com `[agents-webui]` no título
