## Copilot instructions — Eddie Auto-Dev

Purpose: give an AI coding agent the minimal, repo-specific knowledge to be productive immediately.

### Big picture (core architecture)
- **Multi-agent system**: language-specific agents (Python, JS, TS, Go, Rust, Java, C#, PHP) run in isolated Docker containers; each has its own RAG (ChromaDB). See [specialized_agents/README.md](specialized_agents/README.md).
- **Message bus**: all inter-agent activity goes through the singleton bus ([specialized_agents/agent_communication_bus.py](specialized_agents/agent_communication_bus.py)). Do not write directly to DBs/files—publish via the bus. Interceptor ([specialized_agents/agent_interceptor.py](specialized_agents/agent_interceptor.py)) subscribes, assigns `conversation_id`, tracks phases, persists to SQLite or Postgres (`DATABASE_URL`).
- **Orchestration/API**: [specialized_agents/agent_manager.py](specialized_agents/agent_manager.py) + [specialized_agents/api.py](specialized_agents/api.py) manage agent lifecycle, Docker exec, GitHub push. FastAPI on port 8503 by default.
- **Entry points**: Telegram is the main user interface ([telegram_bot.py](telegram_bot.py)); Streamlit dashboard on 8502 ([specialized_agents/conversation_monitor.py](specialized_agents/conversation_monitor.py)).
- **VS Code Extension**: [eddie-copilot/](eddie-copilot/) provides in-editor assistant integration.

### Quick developer workflows ✅
- **Install specialized agents**: `chmod +x specialized_agents/install.sh && ./specialized_agents/install.sh`
- **Start services locally**: `./specialized_agents/start.sh` (Streamlit on 8502, API on 8503)
- **Setup interceptor + test**: `bash setup_interceptor.sh && python3 test_interceptor.py`
- **Run API in dev** (venv): `source .venv/bin/activate && uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503`
- **Run tests**: `pytest -q` (use `-m integration` or `-m external` for marked tests; see [conftest.py](conftest.py))
- **VS Code extension dev**: `cd eddie-copilot && npm install && npm run compile` → Press F5 to launch dev host
- **Check systemd services**: `sudo systemctl status eddie-telegram-bot specialized-agents-api diretor coordinator`
- **View logs**: `journalctl -u <service-name> -f` (e.g., `eddie-telegram-bot`, `specialized-agents-api`)
- **Demo conversations**: `bash demo_conversations.sh`

**Common troubleshooting**:
- If `specialized-agents-api` fails to start → check for missing native deps: `.venv/bin/pip install paramiko` then `sudo systemctl restart specialized-agents-api`
- Postgres setup for cross-process IPC: `docker run -d --name eddie-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres` then add `Environment=DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres` to systemd drop-ins (see [tools/systemd/install_env_for_unit.sh](tools/systemd/install_env_for_unit.sh))

### Project-specific conventions & examples 📚
- **Message-first pattern**: use `log_request`, `log_response`, `log_task_start`, `log_task_end` so metadata like `task_id` is consistent across agents
- **RAG usage**: prefer `RAGManagerFactory.get_manager(language)` or `RAGManagerFactory.global_search(...)`:
  ```py
  from specialized_agents.rag_manager import RAGManagerFactory
  
  # Language-specific RAG
  python_rag = RAGManagerFactory.get_manager("python")
  await python_rag.index_code(code, "python", "descrição")
  results = await python_rag.search("como usar FastAPI")
  
  # Global search across all RAGs
  global_results = await RAGManagerFactory.global_search("docker patterns")
  ```
- **GitHub push** (via manager):
  ```py
  from specialized_agents.agent_manager import get_agent_manager
  manager = get_agent_manager()
  await manager.push_to_github("python", "meu-projeto", repo_name="meu-repo")
  ```
- **Adding a new language agent**:
  1. Add template in [specialized_agents/config.py](specialized_agents/config.py) → `LANGUAGE_DOCKER_TEMPLATES`
  2. Implement agent class in [specialized_agents/language_agents.py](specialized_agents/language_agents.py) (subclass `SpecializedAgent`)
  3. Register the class in `AGENT_CLASSES` and add unit/integration tests

### Remote orchestrator notes ⚠️
- Toggle: `REMOTE_ORCHESTRATOR_ENABLED`; hosts configured in `REMOTE_ORCHESTRATOR_CONFIG['hosts']`.
- Hosts are attempted in order (e.g., `localhost` → `homelab`).
- **Note:** GitHub-hosted runners cannot reach private networks (e.g., 192.168.*.*). For SSH-based workflows, prefer a self-hosted runner in the homelab or expose a secured endpoint.

### Integration points & env vars (used across scripts)
- `OLLAMA_HOST` (default `http://192.168.15.2:11434`) — used by `telegram_bot.py` and many agent flows.
- `GITHUB_AGENT_URL` (local helper at `http://localhost:8080`).
- `DATA_DIR` / `DATABASE_URL` for interceptor persistence.
- Do not log or commit secrets; use `tools/vault/secret_store.py` or `tools/simple_vault/`.

### Testing & CI tips 🧪
- Integration tests expect running services (API + interceptor). See [test_api_integration.py](test_api_integration.py) and [conftest.py](conftest.py) for markers and skips
- Use `pytest -q`; CI toggles may enable `integration`/`external` marks explicitly
- Test markers defined in conftest.py:
  - `@pytest.mark.integration` - tests requiring local services (API on 8503)
  - `@pytest.mark.external` - tests using external libs (chromadb, paramiko, playwright)
- Be mindful of cleanup policies (backup retention, container cleanup) during tests

---

### Essenciais operacionais ⚠️
- **DB-backed IPC** (cross-process): use Postgres + [tools/agent_ipc.py](tools/agent_ipc.py). **Defina `DATABASE_URL`** nas services (systemd drop-ins ou arquivos de ambiente) para que `diretor`, `coordinator` e `specialized-agents-api` troquem mensagens:
  ```py
  from tools import agent_ipc
  rid = agent_ipc.publish_request('assistant','DIRETOR','Please authorize',{})
  resp = agent_ipc.poll_response(rid, timeout=60)
  print(resp)
  ```
- Se `specialized-agents-api` falhar no startup, verifique dependências nativas (ex.: `paramiko`). Exemplo de correção: `.venv/bin/pip install paramiko` && `sudo systemctl restart specialized-agents-api`
- **Systemd tips**: adicione drop-ins em `/etc/systemd/system/<unit>.d/env.conf` para exportar `DATABASE_URL`, depois `sudo systemctl daemon-reload && sudo systemctl restart <unit>`
- **Deploy do site**: veja [site/deploy/](site/deploy/) (`openwebui-ssh-tunnel.service`, nginx, `cloudflared`). Health checks verificam `http://192.168.15.2:3000/health` (resposta `000000` indica problema de rede/túnel)

### Exemplos rápidos 📤
- **Publish coordinator broadcast** (API):
```bash
curl -X POST http://localhost:8503/communication/publish \
  -H 'Content-Type: application/json' \
  -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
```
- **Invoke Diretor** (local helper):
```bash
python3 tools/invoke_director.py "Please review my deployment plan"
```

> Para detalhes operacionais (comandos longos, Docker quickstart, drop-in examples), consulte [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md).

### Minimal example (bus publish) 📤
```py
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
bus = get_communication_bus()
bus.publish(MessageType.REQUEST, "caller", "target_agent", {"op": "run"}, metadata={"task_id": "t1"})
```

If anything is unclear or missing, point to the section (architecture, workflows, conventions) and I will refine it. See [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md) for expanded troubleshooting, examples, and deploy tips.
