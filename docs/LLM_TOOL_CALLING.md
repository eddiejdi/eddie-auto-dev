# LLM Tool Calling — Documentação Completa

> Permite que modelos LLM executem comandos reais no sistema (shell, leitura de arquivos, info do sistema) de forma transparente e segura.

---

## 📐 Arquitetura

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ABORDAGEM A: Open WebUI                          │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  Usuário  │───▶│  Open WebUI  │───▶│  Ollama  │    │  Eddie API   │  │
│  │  Browser  │    │    :8510     │◀───│  :11434  │    │    :8503     │  │
│  └──────────┘    │   (Tool)     │────────────────▶│/llm-tools/*   │  │
│                  │              │◀───────────────│              │  │
│                  └──────────────┘                  └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                     ABORDAGEM B: Proxy Interceptor                      │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  Client   │───▶│ LLM Optimizer│───▶│  Ollama  │    │  Eddie API   │  │
│  │(Cline/API)│    │ Proxy :8512  │◀───│  :11434  │    │    :8503     │  │
│  └──────────┘    │ Interceptor  │────────────────▶│/llm-tools/*   │  │
│                  │              │◀───────────────│              │  │
│                  └──────────────┘                  └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       ABORDAGEM C: API Direta                           │
│                                                                         │
│  ┌──────────┐    ┌──────────────────────────────────────────────────┐  │
│  │  Client   │───▶│              Eddie API :8503                    │  │
│  │(CLI/curl) │    │  POST /llm-tools/chat                          │  │
│  └──────────┘    │  (chama Ollama + executa tools internamente)    │  │
│                  └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Tools Disponíveis (4)

| Tool | Descrição | Parâmetros |
|------|-----------|------------|
| `shell_exec` | Executa comandos shell | `command` (str), `timeout` (int), `cwd` (str) |
| `read_file` | Lê conteúdo de arquivos | `filepath` (str), `max_lines` (int) |
| `list_directory` | Lista diretórios | `dirpath` (str), `recursive` (bool) |
| `system_info` | Info do sistema | _(nenhum)_ |

### Segurança (Whitelist)

**Comandos permitidos** (7 categorias):
- `system`: uname, hostname, uptime, whoami, id, date, df, free, lsblk, top, ps, cat /proc/*
- `docker`: docker ps/logs/inspect/stats/images/restart/exec/compose
- `systemd`: systemctl status/list-units/restart/start/stop, journalctl
- `git`: git status/log/diff/branch/remote/show
- `network`: curl, wget, ping, ss, ip, nslookup, dig, traceroute, netstat
- `files`: find, grep, ls, cat, head, tail, wc, du, stat, file, echo, touch, tee, sort, uniq, cut, awk, sed, xargs, basename, dirname, realpath, readlink
- `dev`: pip list/show/install, python3, node, npm, go, cargo, dotnet, php, javac, java, make

**Comandos bloqueados**: `rm -rf /`, `dd of=/dev`, `mkfs`, `shred`, `chmod 777 /`

**Paths permitidos**: `/home`, `/tmp`, `/opt`, `/etc`, `/var/log`

---

## ⚡ Protocolo Ollama Native Tool Calling

O Ollama suporta tool calling nativo a partir da v0.4+. O formato segue:

### Request (com tools)

```json
POST /api/chat
{
  "model": "qwen3:8b",
  "messages": [
    {"role": "system", "content": "You are Eddie, an AI assistant with tool execution capabilities..."},
    {"role": "user", "content": "qual o status do docker?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "shell_exec",
        "description": "Execute a shell command...",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {"type": "string", "description": "Shell command to execute"}
          },
          "required": ["command"]
        }
      }
    }
  ],
  "stream": false
}
```

### Response (com tool_calls)

```json
{
  "message": {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "function": {
          "name": "shell_exec",
          "arguments": {"command": "docker ps --format 'table {{.Names}}\t{{.Status}}'"}
        }
      }
    ]
  }
}
```

### Re-envio com resultado

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "qual o status do docker?"},
    {"role": "assistant", "content": "", "tool_calls": [...]},
    {"role": "tool", "content": "NAMES          STATUS\neddie-postgres  Up 3 days\ngrafana         Up 5 hours"}
  ],
  "tools": [...],
  "stream": false
}
```

### Modelos com suporte

`qwen3` · `qwen2.5` · `qwen2.5-coder` · `llama3.1+` · `mistral` · `mistral-nemo` · `command-r-plus` · `granite3` · `eddie-coder` · `eddie-tools`

---

## 🅰️ Abordagem A: Open WebUI Tool

**Arquivo**: `openwebui_tool_executor.py`

### Instalação

1. Abra Open WebUI: http://192.168.15.2:8510
2. Vá em **Workspace → Tools → "+"**
3. Cole o conteúdo de `openwebui_tool_executor.py`
4. Salve com nome "Eddie Tool Executor"
5. A tool ficará disponível para todos os modelos

### Via API

```bash
curl -X POST http://localhost:8510/api/v1/tools/create \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "eddie-tool-executor",
    "name": "Eddie Tool Executor",
    "content": "'"$(cat openwebui_tool_executor.py)"'",
    "meta": {"description": "Execute commands on homelab via Eddie API"}
  }'
```

### Valves (Configuração)

| Valve | Default | Descrição |
|-------|---------|-----------|
| `EDDIE_API_URL` | `http://localhost:8503` | URL da API Eddie |
| `TOOL_TIMEOUT` | `60` | Timeout em segundos |

### Como funciona

1. Usuário pergunta no Open WebUI: "qual o status do docker?"
2. Open WebUI envia request com `tools` ao Ollama
3. Ollama retorna `tool_call: shell_exec(command="docker ps")`
4. Open WebUI executa a Tool → chama `POST /llm-tools/execute` na API :8503
5. Resultado volta ao Ollama para interpretação
6. Usuário recebe resposta formatada

---

## 🅱️ Abordagem B: Proxy Interceptor

**Arquivo**: `tools/proxy_tool_interceptor.py`

### Deploy no Homelab

```bash
# 1. Copiar para o homelab
scp tools/proxy_tool_interceptor.py homelab@192.168.15.2:~/llm-optimizer/

# 2. No homelab, editar llm_optimizer_v2.3.py:
ssh homelab@192.168.15.2
cd ~/llm-optimizer
```

### Integração no Proxy

```python
# No topo do llm_optimizer_v2.3.py:
from proxy_tool_interceptor import ToolInterceptor, create_tool_middleware

# Após criar o app FastAPI:
tool_interceptor = ToolInterceptor(
    executor_url="http://localhost:8503",
    ollama_host="http://127.0.0.1:11434",
    max_rounds=10,
)

# OPÇÃO A: Middleware automático
create_tool_middleware(app, tool_interceptor)

# OPÇÃO B: Manual (no handler existente)
async def enhanced_chat(body: dict) -> dict:
    body = tool_interceptor.inject_tools(body)
    response = await forward_to_ollama(body)
    if tool_interceptor.has_tool_calls(response):
        response = await tool_interceptor.handle_tool_loop(body, response)
    return response
```

### API do Interceptor

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/tool-interceptor/stats` | GET | Estatísticas de uso |
| `/tool-interceptor/tools` | GET | Lista tools disponíveis |

### Comportamento

- **Injeção automática**: Se o request não tem `tools` e o modelo suporta → injeta automaticamente
- **Stream**: Desabilitado durante tool calling (necessário para tool_calls)
- **System message**: Injetado se não houver role=system nas messages
- **Transparente**: Client não precisa saber que tools foram injetadas

---

## 🅲 Abordagem C: API Direta

### POST /llm-tools/chat

Endpoint agentic completo na API Eddie (:8503). Gerencia o loop inteiro.

```bash
curl -X POST http://localhost:8503/llm-tools/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "qual o status do docker?",
    "model": "qwen3:8b",
    "use_native_tools": true,
    "max_rounds": 5
  }'
```

**Response:**
```json
{
  "response": "NAMES          STATUS\neddie-postgres  Up 3 days\n...",
  "tools_used": ["shell_exec"],
  "rounds": 1,
  "mode": "native",
  "conversation_id": "abc123..."
}
```

### GET /llm-tools/ollama-tools-schema

Retorna as tools no formato nativo Ollama.

```bash
curl http://localhost:8503/llm-tools/ollama-tools-schema | jq
```

---

## 🖥️ CLI Client

**Arquivo**: `llm_tool_client.py`

### Uso

```bash
# Modo nativo (padrão) — usa tools parameter do Ollama
python3 llm_tool_client.py "qual o status do docker?"

# Modo legacy — usa tags <tool_call>
python3 llm_tool_client.py --legacy "docker ps"

# Interativo
python3 llm_tool_client.py -i

# Interativo verbose com modelo específico
python3 llm_tool_client.py -i -v --model qwen3:8b

# Estatísticas de aprendizado
python3 llm_tool_client.py --stats
```

### Comandos interativos

| Comando | Ação |
|---------|------|
| `sair` | Encerra sessão |
| `stats` | Mostra estatísticas de aprendizado |
| `limpar` | Limpa histórico da conversa |
| `historico` | Mostra execuções realizadas |
| `modo` | Alterna entre nativo e legacy |

---

## 🧠 Sistema de Aprendizado

O executor integra com `AgentMemory` (PostgreSQL) para:

1. **Registrar decisões**: cada tool execution é registrada com confiança
2. **Consultar histórico**: antes de executar, verifica decisões passadas similares
3. **Atualizar feedback**: sucesso/falha ajusta a confiança futura
4. **Publicar no bus**: todas as execuções são publicadas no `AgentCommunicationBus`

### Confiança

| Resultado | Confiança |
|-----------|-----------|
| Sucesso | 0.85 |
| Falha | 0.45 |
| Exceção | 0.20 |
| Máximo | 0.98 |

### Uso programático

```python
from specialized_agents.llm_tool_executor_enhanced import get_enhanced_executor

executor = get_enhanced_executor()
result = await executor.execute_with_learning(
    tool_name="shell_exec",
    params={"command": "docker ps"},
    context={"source": "user_request", "conversation_id": "abc123"}
)
# result["_learning"] contém decision_id, past_decisions, confidence
```

---

## 📁 Arquivos do sistema

| Arquivo | Descrição |
|---------|-----------|
| `specialized_agents/llm_tool_executor.py` | Executor base com whitelist de segurança |
| `specialized_agents/llm_tool_executor_enhanced.py` | Executor com AgentMemory + Bus |
| `specialized_agents/llm_tool_schemas.py` | Schemas nativos Ollama (JSON Schema) |
| `specialized_agents/llm_tool_prompts.py` | System prompt com tags (modo legacy) |
| `specialized_agents/llm_tools_api.py` | Rotas FastAPI |
| `openwebui_tool_executor.py` | Tool para Open WebUI |
| `tools/proxy_tool_interceptor.py` | Interceptor para proxy LLM Optimizer |
| `llm_tool_client.py` | CLI client interativo |
| `models/Modelfile.eddie-tools` | Modelfile Ollama customizado |
| `tests/test_llm_tools.py` | Testes unitários |

---

## 🔧 Troubleshooting

### LLM retorna instruções em texto em vez de executar

**Causa**: modelo não recebeu `tools` parameter → não sabe que pode chamar ferramentas.
**Solução**: use `--native` (padrão) no client ou verifique que o proxy injetou tools.

### Tool não encontrada

**Causa**: tool_name inválido ou não está na whitelist.
**Solução**: verificar `GET /llm-tools/available` para listar tools e comandos permitidos.

### Timeout na execução

**Causa**: comando demora mais que 30s (default).
**Solução**: aumentar `timeout` no params da tool (max 300s).

### Stream não funciona com tools

**Comportamento esperado**: tool calling requer `stream: false`. O interceptor desabilita stream automaticamente quando injeta tools. A resposta final é retornada completa.

### Modelo não suporta tools

**Solução**: usar modelo com suporte (qwen3, qwen2.5-coder, llama3.1+). Verificar com:
```bash
ollama show <model> | grep -i tool
```

---

## 🚀 Roadmap

- [ ] Pipeline de tools (saída de uma → entrada da próxima)
- [ ] Tool `web_search` (busca na internet)
- [ ] Tool `database_query` (queries PostgreSQL)
- [ ] Tool `git_operations` (commit, push, branch)
- [ ] Dashboard Grafana com métricas de tool usage
- [ ] Rate limiting por tool/usuário
- [ ] Approval workflow para comandos críticos
