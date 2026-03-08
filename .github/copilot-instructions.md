## Copilot Instructions — Shared Auto-Dev (Sumário)

> **Instruções detalhadas são modulares** — veja `.github/instructions/*.md` (carregados automaticamente por `applyTo` glob).
> Este arquivo contém APENAS as regras mais críticas que se aplicam a TODO contexto.

### Arquitetura (visão geral)
- **Multi-agent system** Python com FastAPI (porta 8503), Telegram Bot, PostgreSQL, Ollama dual-GPU.
- **Message bus**: `specialized_agents/agent_communication_bus.py` — toda comunicação inter-agente passa pelo bus.
- **Orchestration/API**: `specialized_agents/api.py` + `agent_manager.py`. Streamlit em 8502.
- **IPC cross-process**: `tools/agent_ipc.py` (requer `DATABASE_URL`).

### Regras obrigatórias (TODAS as interações)

**Python:**
- Type hints em TODAS as funções. Docstrings em PT-BR.
- async/await para I/O. f-strings (nunca .format). pathlib (nunca os.path).
- try/except específico com logging. Nunca `print()` em produção.
- Imports: stdlib → third-party → local.

**Banco de dados (trading):**
- **SOMENTE PostgreSQL** (psycopg2) — porta 5433, schema btc. **NUNCA SQLite**.
- `conn.autocommit = True`. Placeholders `%s`. Filtrar `AND symbol=%s`.
- `dry_run` é `bool` (True/False), nunca int.

**Comportamento do agente:**
- Executar, não explicar. 1 tarefa = 1 turno completo.
- Máximo 1 arquivo .md por tarefa. Validar após cada ação.
- Nunca commit secrets — usar `tools/vault/secret_store.py`.
- **Sempre mantenha o GH limpo após as alterações**: `git status` deve estar vazio (sem arquivos modificados não-commitados). Use `git restore .` e `git clean -fd` se necessário.

**🧪 TESTES UNITÁRIOS — IMPEDITIVO GLOBAL:**
- ⚠️ **CRÍTICO**: TODA correção/feature deve incluir testes unitários
- Cobertura mínima: 80% do código novo
- Padrão: `tests/test_<modulo>.py` com `pytest` + `pytest-cov`
- Executar: `pytest --cov=<path> -q` antes de commitar
- Fixtures: Usar padrão conftest.py, fixtures reutilizáveis
- Mocking: Mock IOs externos (DB, HTTP, APIs), NUNCA use APIs reais em testes
- Sem testes = NÃO MERGEABLE, mesmo que código esteja correto
- Padrão: Testes devem passar com `pytest -q` sem warnings

**LLM routing (GPU-FIRST GLOBAL RULE):**
- ⚠️ **CRITICAL**: GPU0 (`:11434`) e GPU1 (`:11435`) SEMPRE antes de qualquer API cloud
- **NUNCA use tokens GitHub/OpenAI/Anthropic/Google sem tentativa DUPLA no Ollama local**
- Estratégia de fallback: GPU0 → GPU1 → (somente então considerar cloud com aprovação)
- Modelos gratuitos cloud APENAS se ambos GPUs indisponíveis: GPT-4o/4.1/5.1
- **PROIBIDOS em ALL contexts**: Claude Opus/Sonnet, o3, Gemini Pro, GPT-4 Turbo
- Configuração: `OLLAMA_HOST=http://192.168.15.2:11434`, `OLLAMA_HOST_GPU1=http://192.168.15.2:11435`

**Serviços críticos — NUNCA reiniciar sem confirmar:**
- ssh/sshd, pihole-FTL, docker, networking, ufw, systemd-resolved.

**VS Code window colors:**
- `python tools/vscode_window_state.py <processing|done|error|prompt> --agent-id <id>`

### Quick workflows
- **API dev**: `source .venv/bin/activate && uvicorn specialized_agents.api:app --port 8503`
- **Tests**: `pytest -q` (`-m integration` / `-m external`)
- **Services**: `sudo systemctl status shared-telegram-bot specialized-agents-api`
- **Logs**: `journalctl -u <service> -f`

### Env vars essenciais
- `OLLAMA_HOST` = `http://192.168.15.2:11434` (GPU0 RTX 2060)
- `OLLAMA_HOST_GPU1` = `http://192.168.15.2:11435` (GPU1 GTX 1050)
- `OLLAMA_MODEL` = `shared-coder`
- `DATABASE_URL` — para IPC cross-process
- `DATA_DIR` — persistência local

### Módulos de instrução (carregados on-demand por applyTo)
| Arquivo | Aplica quando |
|---------|---------------|
| `instructions/python-coding.md` | Editando `*.py` |
| `instructions/trading-database.md` | Arquivos trading/btc/exporter/coin |
| `instructions/infrastructure.md` | Homelab/docker/systemd/ssh/deploy |
| `instructions/ollama-llm.md` | Ollama/LLM/token/agent |
| `instructions/testing.md` | test*/conftest/spec/pytest |
| `instructions/vscode-extension.md` | shared-copilot/ts/js |
