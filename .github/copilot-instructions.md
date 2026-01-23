## Copilot instructions — Eddie Auto-Dev (concise)

Goal: give an AI coding agent the minimal, high-value knowledge to be productive in this repo.

- Quick start (local):
  - `bash setup_interceptor.sh` — installs and configures local dev pieces.
  - `streamlit run specialized_agents/conversation_monitor.py --server.address 0.0.0.0 --server.port 8501` — realtime dashboard.
  - `python3 test_interceptor.py` — primary smoke + unit validation.

- Where to look first (fast tour):
  - Agent comms & runtime: `specialized_agents/agent_communication_bus.py`, `specialized_agents/agent_interceptor.py`.
  - Orchestration & API: `specialized_agents/agent_manager.py`, `specialized_agents/api.py`.
  - Agent implementations: `specialized_agents/language_agents.py`, `specialized_agents/agent_rag/`, `specialized_agents/rag_manager.py`.
  - Bot entry: `telegram_bot.py` (contains AutoDeveloper flows and INABILITY_PATTERNS).

- Important env, services, and integrations:
  - Ollama host default: `http://192.168.15.2:11434`. Set `OLLAMA_HOST` in your `.env` when different.
  - Systemd service names you may interact with: `eddie-telegram-bot`, `specialized-agents`, `specialized-agents-api`.
  - Secrets: prefer `tools/vault/secret_store.py` (Bitwarden). Fallback: `tools/simple_vault/` (GPG files). Do not print secrets.
  - Fly.io tunnel is critical — read `CRITICAL_FLYIO_TUNNEL.md` before making tunnel changes.

- Hard conventions (follow exactly):
  - Always send agent actions through the message bus: call `get_communication_bus()` then `bus.publish(...)`. Never write directly to agent DBs/files — use managers in `specialized_agents/`.
  - Adding a new language agent: add a Docker template in `specialized_agents/config.py` (`LANGUAGE_DOCKER_TEMPLATES`), implement wiring in `specialized_agents/language_agents.py`, register the class in `AGENT_CLASSES`, and add tests + docs.
  - Commit message style: `feat|fix|test|refactor: short description`. Use feature branches; ensure tests pass before PR.

- Tests & quick checks:
  - Run full checks: `bash setup_interceptor.sh && python3 test_interceptor.py`.
  - Start API locally: `uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503` and check `curl http://localhost:8503/status`.
  - Simulate conversations: `bash demo_conversations.sh` to exercise dashboard flows.

- Common developer patterns to follow (examples):
  - Message bus usage: see `specialized_agents/agent_communication_bus.py` for `publish()` payload shapes and `specialized_agents/agent_interceptor.py` for handlers.
  - RAG & embeddings: `specialized_agents/rag_manager.py` and `specialized_agents/agent_rag/` contain the retrieval + embed workflows.
  - GitHub automation: `specialized_agents/github_client.py` shows how PRs and pushes are integrated with CI checks.

- Infra & safety notes:
  - For infra changes (systemd, Fly, secrets), request human approval and include exact commands and backup paths (backups stored under `/home/homelab/backups/`).
  - Never leak credentials to logs or stdout. Use `tools/vault/secret_store.py` for automated secret actions when possible.

- Quick actionable examples (copy-paste):
  - Start dashboard: `streamlit run specialized_agents/conversation_monitor.py`
  - Run API: `uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503`
  - Run tests: `python3 test_interceptor.py`

If anything here is unclear or you'd like a targeted expansion (e.g., step-by-step: "How to add a new agent" or a CI PR template enforcing `test_interceptor.py`), tell me which section to expand.
