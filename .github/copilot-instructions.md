## Copilot instructions — Eddie Auto-Dev

Purpose: give an AI coding agent the minimal, repo-specific knowledge to be productive immediately.

### Big picture (core architecture)
- Multi-agent system: language-specific agents run in isolated Docker containers; each has its own RAG (ChromaDB). See `specialized_agents/README.md`.
- All inter-agent activity must go through the message bus (`specialized_agents/agent_communication_bus.py`). Do not write directly to DBs/files—use the bus and managers.
- The interceptor (`specialized_agents/agent_interceptor.py`) subscribes to the bus, assigns/uses `conversation_id`, tracks phases, and persists to SQLite (or `DATABASE_URL`).
- Orchestration/API lives in `specialized_agents/agent_manager.py` + `specialized_agents/api.py` (agent lifecycle, Docker exec, GitHub push).
- Telegram is the main user entrypoint and integration hub (`telegram_bot.py`).

### Critical workflows (commands used in this repo)
- Setup/validate interceptor: `bash setup_interceptor.sh` then `python3 test_interceptor.py`.
- Run API: `uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503` (health: `/health`).
- Streamlit dashboard: `streamlit run specialized_agents/conversation_monitor.py`.
- Demo flow: `bash demo_conversations.sh`.

### Project-specific conventions
- Message-first: use helper log wrappers (`log_request`, `log_response`, `log_task_start`, `log_task_end`) so metadata like `task_id` is consistent.
- New agent flow: add template in `specialized_agents/config.py` (`LANGUAGE_DOCKER_TEMPLATES`) → implement in `specialized_agents/language_agents.py` → register in `AGENT_CLASSES` → add tests/docs.
- RAG access: prefer `RAGManagerFactory.get_manager(language)` or `RAGManagerFactory.global_search(...)` from `specialized_agents/rag_manager.py`.
- Secrets: use `tools/vault/secret_store.py` or `tools/simple_vault/`; never hardcode or print secrets.

### Integration points & env vars (used across scripts)
- `OLLAMA_HOST` (default references point to `http://192.168.15.2:11434`).
- `GITHUB_AGENT_URL` (local helper at `http://localhost:8080`).
- `DATA_DIR` / `DATABASE_URL` for interceptor persistence.

### Minimal example (bus publish)
```py
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
bus = get_communication_bus()
bus.publish(MessageType.REQUEST, "caller", "target_agent", {"op": "run"}, metadata={"task_id": "t1"})
```

If anything is unclear or missing, point to the section (architecture, workflows, conventions) and I will refine it.
