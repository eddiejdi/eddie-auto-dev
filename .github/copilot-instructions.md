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
- **VS Code extension dev**: 
  ```bash
  cd eddie-copilot
  npm install              # Install dependencies
  npm run compile          # Compile TypeScript
  npm run watch            # Watch mode for development
  # Press F5 in VS Code to launch Extension Development Host
  # Or: vsce package && code --install-extension eddie-copilot-*.vsix
  ```
- **Check systemd services**: `sudo systemctl status eddie-telegram-bot specialized-agents-api diretor coordinator`
- **View logs**: `journalctl -u <service-name> -f` (e.g., `eddie-telegram-bot`, `specialized-agents-api`)
- **Demo conversations**: `bash demo_conversations.sh`

**Common troubleshooting**:
- If `specialized-agents-api` fails to start → check for missing native deps: `.venv/bin/pip install paramiko` then `sudo systemctl restart specialized-agents-api`
  - Postgres setup for cross-process IPC: `docker run -d --name eddie-postgres -e POSTGRES_PASSWORD=eddie_memory_2026 -p 5432:5432 postgres` then add `Environment=DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres` to systemd drop-ins (see [tools/systemd/install_env_for_unit.sh](tools/systemd/install_env_for_unit.sh))

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
  - **Agent Memory System**: persistent memory for learning from past decisions
    ```py
    from specialized_agents.language_agents import PythonAgent
  
    agent = PythonAgent()  # Memory auto-integrated if DATABASE_URL set
  
    # Record decision
    dec_id = agent.should_remember_decision(
      application="my-app", component="auth", error_type="timeout",
      error_message="DB timeout after 5s", decision_type="fix",
      decision="Increase timeout to 30s", confidence=0.8
    )
  
    # Query past decisions
    past = agent.recall_past_decisions("my-app", "auth", "timeout", "DB timeout")
  
    # Informed decision (LLM + memory)
    decision = await agent.make_informed_decision(
      application="my-app", component="auth", 
      error_type="timeout", error_message="DB timeout",
      context={"load": "high"}
    )
  
    # Update feedback after result
    agent.update_decision_feedback(dec_id, success=True, details={"fix_worked": True})
    ```
    See [docs/AGENT_MEMORY.md](docs/AGENT_MEMORY.md) for complete guide.

### Remote orchestrator notes ⚠️
- Toggle: `REMOTE_ORCHESTRATOR_ENABLED`; hosts configured in `REMOTE_ORCHESTRATOR_CONFIG['hosts']`.
- Hosts are attempted in order (e.g., `localhost` → `homelab`).
- **SSH config example** (in [specialized_agents/config.py](specialized_agents/config.py)):
  ```py
  REMOTE_ORCHESTRATOR_CONFIG = {
      "enabled": True,
      "hosts": [
          {"name": "localhost", "host": "127.0.0.1", "user": "root", "ssh_key": None},
          {"name": "homelab", "host": "192.168.15.2", "user": "homelab", "ssh_key": "~/.ssh/id_rsa"}
      ]
  }
  ```
- **Note:** GitHub-hosted runners cannot reach private networks (e.g., 192.168.*.*). For SSH-based workflows, prefer a self-hosted runner in the homelab or expose a secured endpoint.

### � MODELOS GRATUITOS — REGRA OBRIGATÓRIA (TODOS OS AGENTES)
**Use SOMENTE modelos base (gratuitos) do Copilot Pro+.** Modelos premium consomem requests pagos e são proibidos por padrão.
- **Permitidos (base/gratuitos)**: `GPT-4o` · `GPT-4o mini` · `GPT-4.1` · `GPT-4.1 mini` · `GPT-4.1 nano` · `GPT-5.1` · `Raptor Mini`
- **Proibidos (premium)**: `Claude Opus 4` · `Claude Sonnet 4` · `o3` · `o4-mini` · `Gemini 2.5 Pro`
- Se o usuário solicitar explicitamente um modelo premium, avise o custo antes de prosseguir.
- Para tarefas de código/análise: prefira `GPT-4.1` ou `GPT-5.1` (melhor custo-benefício).
- Para completions rápidas: prefira `GPT-4.1 nano` ou `GPT-4o mini`.

### �🔴 ROTEAMENTO HOMELAB — REGRA GLOBAL E IMPERATIVA (TODOS OS AGENTES)
**SEM EXCEÇÃO:** todo agente Copilot (local, distribuído, remoto) DEVE rotear para homelab:
- **Operações para homelab via API** (`POST /distributed/route-task` na porta 8503) **OU SSH direto**:
  - Verificação de logs, status, métricas, saúde
  - Manipulação Docker/systemd/cgroups/iptables
  - BD queries, scrapin, processamento pesado
  - Execução testes, builds, compilação
  - Geração/execução scripts, análise arquivos grandes
- **Permanecer local APENAS**:
  - Análise de documentação
  - Edição de arquivos config simples
  - Orquestração UI, apresentação resultados
  - Resumos (< 100 caracteres) — nunca trazer outputs grandes
- **Benefícios**: economia de tokens Copilot (30-50% redução), melhor performance, recursos homelab maximizados.
- **Exceções SSH direto**: autenticação cloudflared, conectividade crítica, fallback API.
- **Violação = desperdício.** Quando em dúvida: rotear para homelab.

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
    ```py
    @pytest.mark.integration
    def test_api_health():
        response = requests.get('http://localhost:8503/health')
        assert response.status_code == 200
    ```
  - `@pytest.mark.external` - tests using external libs (chromadb, paramiko, playwright)
    ```py
    @pytest.mark.external
    def test_chromadb_connection():
        import chromadb
        client = chromadb.Client()
        assert client.heartbeat() > 0
    ```
- Top-level tests (repo root) ignored by default; set `RUN_ALL_TESTS=1` to collect all
- Be mindful of cleanup policies (backup retention, container cleanup) during tests

---

### Essenciais operacionais ⚠️
- **DB-backed IPC** (cross-process): use Postgres + [tools/agent_ipc.py](tools/agent_ipc.py). **Defina `DATABASE_URL`** nas services (systemd drop-ins ou arquivos de ambiente) para que `diretor`, `coordinator` e `specialized-agents-api` troquem mensagens:
  ```py
  from tools import agent_ipc
  
  # Publish request (from any agent)
  rid = agent_ipc.publish_request('assistant','DIRETOR','Please authorize deploy',{'env':'prod'})
  
  # Poll for response (blocks until Diretor responds or timeout)
  resp = agent_ipc.poll_response(rid, timeout=60)
  if resp:
      print(f"Diretor says: {resp['response']}")
  else:
      print("Timeout waiting for Diretor approval")
  
  # Diretor side (or use tools/invoke_director.py)
  pending = agent_ipc.fetch_pending('DIRETOR')
  for req in pending:
      agent_ipc.respond(req['id'], 'DIRETOR', 'Approved for prod deploy')
  ```
- Se `specialized-agents-api` falhar no startup, verifique dependências nativas (ex.: `paramiko`). Exemplo de correção: `.venv/bin/pip install paramiko` && `sudo systemctl restart specialized-agents-api`
- **Systemd tips**: adicione drop-ins em `/etc/systemd/system/<unit>.d/env.conf` para exportar `DATABASE_URL`, depois `sudo systemctl daemon-reload && sudo systemctl restart <unit>`
- **Deploy do site**: veja [site/deploy/](site/deploy/) (`openwebui-ssh-tunnel.service`, nginx, `cloudflared`). Health checks verificam `http://192.168.15.2:3000/health` (resposta `000000` indica problema de rede/túnel)
- **Test collection**: Top-level test files in repo root are ignored by default to avoid import-time side effects. Set `RUN_ALL_TESTS=1` to override (see [conftest.py](conftest.py))

### Exemplos rápidos 📤
- **Publish coordinator broadcast** (API):
```bash
curl -X POST http://localhost:8503/communication/publish \
  -H 'Content-Type: application/json' \
  -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
- **Invoke Diretor** (local helper):
```bash
python3 tools/invoke_director.py "Please review my deployment plan"
> Para detalhes operacionais (comandos longos, Docker quickstart, drop-in examples), consulte [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md).

### Minimal example (bus publish) 📤
```py
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
bus = get_communication_bus()
bus.publish(MessageType.REQUEST, "caller", "target_agent", {"op": "run"}, metadata={"task_id": "t1"})
If anything is unclear or missing, point to the section (architecture, workflows, conventions) and I will refine it. See [.github/copilot-instructions-extended.md](.github/copilot-instructions-extended.md) for expanded troubleshooting, examples, and deploy tips.