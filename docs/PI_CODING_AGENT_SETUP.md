# Pi Coding Agent — setup (Shared Auto-Dev)

Guia de instalação e operação do [Pi](https://pi.dev/) neste workstation, como **harness auxiliar** (não substitui Claude Code, Codex nem Grok Build).

## Papel no stack

| Harness | Uso |
|---------|-----|
| Claude Code / Grok Build | Trabalho pesado multi-file |
| Codex | OpenAI / plugins |
| **Pi + Ollama** | Local, barato, fallback; **com os mesmos guardrails Python** |
| OpenCode | Já instalado; coexistente |
| specialized_agents / systemd | Domínio 24/7 |

## Requisitos

- **Node.js ≥ 22.19** (Pi 0.82+). Neste host: `~/.local/node-v22.19.0` + symlinks em `~/.local/bin/node`.
- npm global prefix: `~/.local`
- Ollama com modelos **aprovados** (não chineses)
- Endpoint real dos modelos: `OLLAMA_HOST=http://192.168.15.2:11434` (homelab).  
  O serviço local `127.0.0.1:11434` pode estar vazio — **não** use como default do Pi.

### Modelos aprovados (política 2026-07-01)

Usar: **Llama, Mistral, Gemma, Phi**  
Proibido: **Qwen, DeepSeek, ERNIE, ChatGLM, InternLM, Baichuan, Yi-coder**, etc.

Default configurado: `llama3.1:8b` via provider `ollama`.

## Instalação

```bash
export PATH="$HOME/.local/bin:$HOME/.local/node-v22.19.0/bin:$PATH"
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
pi --version
```

### Uninstall

```bash
npm uninstall -g @earendil-works/pi-coding-agent
# opcional: rm -rf ~/.pi
```

## Config global

| Arquivo | Função |
|---------|--------|
| `~/.pi/agent/settings.json` | default provider/model, telemetry off, compaction |
| `~/.pi/agent/models.json` | Ollama em `http://192.168.15.2:11434/v1` |
| `~/.pi/agent/trust.json` | trust do monorepo (carrega `.pi/extensions`) |
| `~/.pi/agent/auth.json` | só se usar cloud login |

## Config do monorepo

| Path | Função |
|------|--------|
| `AGENTS.md` | contexto curto do projeto |
| `.pi/settings.json` | override provider/model |
| `.pi/extensions/rpa4all-hooks/` | bridge de hooks Python |
| `.pi/extensions/rpa4all-protected-paths.ts` | block write em paths sensíveis |

Trust (se ainda não existir):

```bash
# ou /trust dentro do TUI
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home()/".pi/agent/trust.json"
data = json.loads(p.read_text()) if p.exists() else {}
data[str(Path("/workspace/eddie-auto-dev").resolve())] = True
p.write_text(json.dumps(data, indent=2)+"\n")
PY
```

Headless com resources de projeto:

```bash
cd /workspace/eddie-auto-dev
pi -p --provider ollama --model llama3.1:8b --approve "..."
```

## Hooks (arquitetura)

Pi **não** usa `hooks.json`. Extensions TypeScript escutam eventos e chamam os scripts Claude:

```text
Pi tool_call → bridge.ts → python3 tools/.../*.py (stdin JSON)
                ← JSON permissionDecision deny|ask|allow
```

Mapa completo: `.pi/extensions/rpa4all-hooks/README.md`

| Claude | Pi |
|--------|-----|
| PreToolUse | `tool_call` → `{ block: true }` |
| ask | UI confirm; headless = block |
| PostToolUse | `tool_result` (notify) |
| Stop | `agent_settled` (notify; sem loop forçado idêntico) |
| additionalContext / MEMORY | `before_agent_start` custom message |

**Fonte de verdade:** `tools/copilot_hooks/*` e `tools/hooks/*` — não reimplementar regras em TS.

### Adicionar um novo hook Python

1. Criar/ajustar script no estilo Claude (stdin JSON → stdout JSON).
2. Registrar em `PRE_TOOL_HOOKS` / `POST_TOOL_HOOKS` / `STOP_HOOKS` em `.pi/extensions/rpa4all-hooks/bridge.ts`.
3. Reiniciar sessão Pi ou `/reload`.

## Uso diário

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /workspace/eddie-auto-dev
pi
# /model  → escolher ollama/llama3.1:8b
# /trust  → se extensions não carregarem
```

Print mode:

```bash
pi -p --provider ollama --model llama3.1:8b --approve "Responda só: pong"
```

## Smoke checklist

1. `pi --version` → 0.82.x+
2. `curl -s http://192.168.15.2:11434/v1/chat/completions ... llama3.1:8b` → pong
3. `pi -p ... "Responda só: pong"` → pong
4. Sessão mostra `rpa4all-hooks loaded` (ou log)
5. Agent tenta `rm -rf ...` → **block** (`[rpa4all-hooks] warning: ⛔ ...`)
6. Agent tenta `ltfsck` → **block**
7. Write em path `.env` → **block** (protected-paths +/ou guardrails)
8. Write em `/tmp/pi-ok.txt` → allow

Smokes validados neste host (2026-07-26): pong OK; `rm -rf` bloqueado 2× pelo bridge; Python deny para `ltfsck` OK.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| `model not found` em 127.0.0.1 | Ollama local vazio | Usar `192.168.15.2:11434` em `models.json` |
| Extensions não rodam | projeto não trusted | `/trust` ou `trust.json` |
| `Unsupported engine` Node 20 | Pi exige ≥22.19 | usar `~/.local/node-v22.19.0` no PATH |
| Hooks não bloqueiam | payload tool name | ver `payload.ts` mapeamento |
| Qwen como default | config errada | default `llama3.1:8b`; guardrail bloqueia pull/run qwen |
| Modelo local “enlouquece” / não responde pong | MEMORY.md grande no prompt | `export PI_MEMORY_MAX_CHARS=800` (default 1200) |

## Segurança

- Pi **não** tem sandbox built-in (mesma conta do usuário).
- Packages de terceiros (`pi install npm:...`) rodam código arbitrário — **não** instalados nesta onda.
- Automação headless: preferir container + secrets mínimos.

## Referências

- Site: https://pi.dev/
- Docs: https://pi.dev/docs/latest
- Extensions: https://pi.dev/docs/latest/extensions
- Hooks Claude (fonte): `.claude/settings.json`, `hooks.json`
