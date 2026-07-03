# Codex Agent — MCP Server

## Informações Básicas

| Campo | Valor |
|-------|-------|
| **Tipo** | MCP Server (stdio, local) |
| **Script** | `scripts/codex_mcp_server.py` |
| **Repo homelab** | `/apps/codex-agent/` em `192.168.15.2` |
| **Registro** | `.mcp.json` → `codex-agent` |
| **Criado** | 2026-06-23 |
| **Modelo padrão** | `gpt-5.4-mini` (automático) |

## Objetivo

Dividir a carga de tokens do Claude delegando tarefas de código a um agente Codex mais barato. O Claude orquestra; o Codex executa implementações, reviews e buscas autônomas no workspace.

```
Claude (orquestrador)
    ↓ MCP call via .mcp.json
codex_mcp_server.py  ←  roda localmente, auth já existe em ~/.codex/
    ↓ classifica complexidade do prompt
codex exec --model <auto> --sandbox workspace-write --json -C <cwd>
    ↓ gpt-5.4-mini / gpt-5.4 / gpt-5.5
Resposta final + uso de tokens
    ↓ (notificação opcional)
homelab bus  →  coordinator
```

## Roteamento Automático de Modelo

A seleção acontece em `select_model(prompt, hint)` com três camadas de prioridade:

```
1. MAX_TRIGGERS (keywords pesadas)   →  gpt-5.5
   "refactor entire", "migrate", "architect", "overhaul",
   "rewrite", "major refactor", "entire codebase", >600 palavras

2. PRO_TRIGGERS (keywords médias)    →  gpt-5.4
   "implement", "create", "build", "debug", "fix bug",
   "write tests", "add tests", "add unit", "handle error"

3. MINI_TRIGGERS ou curto (<80w)     →  gpt-5.4-mini
   "fix typo", "explain", "list", "format", "rename",
   "docstring", "clarify", "summarize"
```

O caller pode sempre sobrescrever com `model_hint`:
```json
{"name": "codex_run_task", "arguments": {"prompt": "...", "model_hint": "gpt-5.5"}}
```

### Tabela de Exemplos

| Prompt | Modelo Selecionado |
|--------|--------------------|
| `fix typo in README` | gpt-5.4-mini |
| `explain what HomeAssistantConfig.kt does` | gpt-5.4-mini |
| `add unit tests for HomeAssistantLightController` | gpt-5.4 |
| `implement OAuth2 PKCE flow in auth module` | gpt-5.4 |
| `debug websocket disconnect after 30s` | gpt-5.4 |
| `refactor entire trading agent to async/await` | gpt-5.5 |
| `architect new event-sourced pipeline` | gpt-5.5 |

## Tools MCP

### `codex_run_task`

Executa uma tarefa de código de forma autônoma. Seleciona modelo automaticamente.

```json
{
  "name": "codex_run_task",
  "arguments": {
    "prompt": "string (obrigatório) — instrução detalhada para o Codex",
    "cwd": "string (opcional) — diretório de trabalho absoluto; padrão: ~/workspace",
    "model_hint": "auto | gpt-5.4-mini | gpt-5.4 | gpt-5.5 (padrão: auto)",
    "timeout_s": "int (padrão: 300) — timeout em segundos"
  }
}
```

**Output:**
```
[codex-agent] model=gpt-5.4-mini (21.9s)
<resposta final do agente>

[tokens in=75121 cached=58368 out=779]
```

### `codex_review_code`

Code review não-interativo do repo. Sempre usa `gpt-5.4-mini`.

```json
{
  "name": "codex_review_code",
  "arguments": {
    "cwd": "string (opcional)",
    "focus": "string (opcional) — ex: 'security', 'performance', 'correctness'"
  }
}
```

### `codex_model_info`

Diagnóstico do roteador — retorna modelos disponíveis, heurística ativa e caminho do binário.

```json
{"name": "codex_model_info", "arguments": {}}
```

**Output exemplo:**
```json
{
  "models": {
    "gpt-5.4-mini": "cheap — quick fixes, explain, format, short prompts (<80 words)",
    "gpt-5.4": "medium — implement features, write tests, debug (80–600 words)",
    "gpt-5.5": "expensive — major refactor, architecture, complex migrations (>600 words or heavy keywords)"
  },
  "codex_binary": "/home/edenilson/.vscode/extensions/openai.chatgpt-26.616.71553-linux-x64/bin/linux-x86_64/codex",
  "codex_binary_exists": true,
  "default_workspace": "/workspace/eddie-auto-dev"
}
```

## Configuração (.mcp.json)

```json
"codex-agent": {
  "command": "/workspace/eddie-auto-dev/.venv/bin/python",
  "args": ["/workspace/eddie-auto-dev/scripts/codex_mcp_server.py"],
  "env": {
    "HOMELAB_URL": "http://192.168.15.2:8503",
    "CODEX_WORKSPACE": "/workspace/eddie-auto-dev"
  }
}
```

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `HOMELAB_URL` | `http://192.168.15.2:8503` | URL do coordinator bus para notificações |
| `CODEX_WORKSPACE` | `~/workspace` | Workspace padrão quando `cwd` não é especificado |

## Autenticação

O servidor usa o auth ChatGPT local (`~/.codex/auth.json`). O token de acesso tem validade de ~10 dias; o `refresh_token` renova automaticamente quando o codex CLI é invocado.

**Monitorar validade:**
```bash
python3 -c "
import json, base64, datetime
d = json.load(open('/home/edenilson/.codex/auth.json'))
tok = d['tokens']['access_token']
payload = tok.split('.')[1] + '=='
import base64
decoded = json.loads(base64.b64decode(payload))
exp = datetime.datetime.fromtimestamp(decoded['exp'])
print('Expira em:', exp.isoformat())
print('Hoje:', datetime.datetime.now().isoformat())
"
```

**Se o token expirar:** no VS Code, abrir o painel Codex → Sign In / Reconnect. O `auth.json` será renovado automaticamente.

## Repo Homelab `/apps/codex-agent/`

```
/apps/codex-agent/
├── .git/
├── .github/
│   └── workflows/
│       └── deploy.yml      ← CI: pull + restart service + health check
├── mcp_server.py           ← espelho de scripts/codex_mcp_server.py
├── logs/                   ← logs de execução (futuros)
├── workspace/              ← área de trabalho reservada para tarefas homelab
└── README.md
```

O repo no homelab serve como:
- Espelho auditável do `mcp_server.py`
- Ponto de deploy via `git push` + Actions runner
- Workspace reservado para tarefas autônomas no homelab

**Sincronizar após mudanças no script:**
```bash
scp scripts/codex_mcp_server.py homelab:/apps/codex-agent/mcp_server.py
ssh homelab "cd /apps/codex-agent && git add mcp_server.py && git commit -m 'sync: <descrição>'"
```

## Binário Codex

O binário é fornecido pela extensão VS Code `openai.chatgpt`:

```
~/.vscode/extensions/openai.chatgpt-26.616.71553-linux-x64/bin/linux-x86_64/codex
```

Versão: `codex-cli 0.142.0`

Se a extensão for atualizada, o path do binário muda. O servidor detecta via `codex_binary_exists` no `codex_model_info`. Para atualizar:

```python
# em scripts/codex_mcp_server.py, linha CODEX_BIN:
CODEX_BIN = Path.home() / ".vscode/extensions/openai.chatgpt-<NOVA_VERSAO>-linux-x64/bin/linux-x86_64/codex"
```

Ou usar `find ~/.vscode/extensions -name codex -type f | sort -r | head -1` para descobrir o path atual.

## Sandbox e Segurança

O codex exec roda com:
```
--sandbox workspace-write   # escreve apenas no diretório -C <cwd>
--json                      # output em JSONL (parseado pelo servidor)
-C <cwd>                    # workspace delimitado
```

Não usa `--dangerously-bypass-approvals-and-sandbox`. Aprovações são gerenciadas pelo `trust_level = "trusted"` no `~/.codex/config.toml` para os workspaces conhecidos.

## Troubleshooting

### Codex não carrega no VS Code (tela preta)

```bash
# Matar o app-server travado
kill -9 $(pgrep -f "codex app-server")
# Reload Window no VS Code: Ctrl+Shift+P → Developer: Reload Window
```

### Token expirado — `failed to refresh available models`

```bash
# Verificar validade
cat ~/.codex/auth.json | python3 -c "
import json,sys,base64,datetime
d=json.load(sys.stdin)
tok=d['tokens']['access_token'].split('.')[1]+'=='
p=json.loads(base64.b64decode(tok))
print('exp:', datetime.datetime.fromtimestamp(p['exp']))
"
# Se expirado: VS Code → painel Codex → Sign In
```

### Extensão com versão errada

```bash
find ~/.vscode/extensions -name "codex" -type f 2>/dev/null | sort -r | head -3
# Atualizar CODEX_BIN no script se necessário
```

### Testar MCP server manualmente

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"codex_model_info","arguments":{}}}' | \
.venv/bin/python scripts/codex_mcp_server.py 2>/dev/null
```

### Notificação no bus falhando

O endpoint do bus é `http://192.168.15.2:8503/events`. Falhas são logadas como WARNING e não impedem a execução da task.

```bash
# Verificar bus health
curl http://192.168.15.2:8503/health
```

## Integração com o Coordinator

Após cada task, o servidor publica no bus:

```json
{
  "agent": "codex-agent",
  "event_type": "task_completed",
  "payload": {
    "model": "gpt-5.4-mini",
    "cwd": "/workspace/eddie-auto-dev",
    "exit_code": 0,
    "elapsed_s": 21.9,
    "prompt_words": 7
  }
}
```

Isso permite ao coordinator rastrear carga, latência e custo por modelo.

## Logs

```bash
# Logs em tempo real (stderr do processo MCP)
# No VS Code: Output → MCP Server: codex-agent

# No homelab (futuros logs de execução):
ls /apps/codex-agent/logs/
```

## Limites Conhecidos

| Limitação | Detalhe |
|-----------|---------|
| Auth local | O binário usa `~/.codex/auth.json` local; não roda autônomo no homelab sem sync de auth |
| Timeout | Default 300s; tasks pesadas podem precisar de `timeout_s` maior |
| Modelo fixo na sessão | O `codex mcp-server` nativo não suporta troca de modelo por-call; por isso usa `codex exec` |
| Web search | O Codex pode tentar web search (via `web_search` tool nativo); resultados dependem de conectividade |
| ngs-analysis plugin | Plugin curado com `defaultPrompt` >128 chars — gera warning nos logs, não bloqueia execução |
