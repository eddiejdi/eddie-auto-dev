## Copilot instructions — Eddie Auto-Dev (concise)

Goal: give an AI coding agent the minimal, high-value knowledge to work productively in this repo.

- Quick start (local):
  - `bash setup_interceptor.sh` (installs and configures local dev pieces)
  - `streamlit run specialized_agents/conversation_monitor.py --server.address 0.0.0.0 --server.port 8501`
  - `python3 test_interceptor.py` (run validation tests)

- Where to look first:
  - Agent runtime & comms: `specialized_agents/agent_communication_bus.py` and `specialized_agents/agent_interceptor.py`
  - Agent orchestration: `specialized_agents/agent_manager.py` and `specialized_agents/api.py`
  - Bot entry: `telegram_bot.py` (AutoDeveloper flow, INABILITY_PATTERNS)
  - RAG + embeddings: `specialized_agents/rag_manager.py` and `specialized_agents/agent_rag/`

- Important environment & services:
  - Ollama default: `http://192.168.15.2:11434` (set `OLLAMA_HOST` in `.env`)
  - Systemd services: `eddie-telegram-bot`, `specialized-agents`, `specialized-agents-api`
  - Secrets: `tools/vault/secret_store.py` (Bitwarden wrapper) and repo GPG fallback at `tools/simple_vault/`

- Project-specific conventions (do this exactly):
  - All agent actions must use the message bus (`get_communication_bus()` → `bus.publish(...)`). Do NOT write directly to agent DBs or files — use provided managers.
  - When adding a new agent: add Docker template to `specialized_agents/config.py` (`LANGUAGE_DOCKER_TEMPLATES`), implement in `specialized_agents/language_agents.py`, register in `AGENT_CLASSES`, and add tests + docs.
  - Commit message format: `feat|fix|test|refactor: short description` and push to feature branch before opening PR.

- Tests & validation
  - Primary test runner: `python3 test_interceptor.py` (unit + integration smoke checks)
  - Quick API checks: `curl http://localhost:8503/status` and `curl http://localhost:8503/interceptor/conversations/active`
  - Use `bash demo_conversations.sh` to simulate agent dialogs for the dashboard.

- Integrations & deployment notes
  - Fly.io tunnel is critical; see `CRITICAL_FLYIO_TUNNEL.md` and `install_tunnel.sh` — do not rotate OAuth secrets without backups in `/home/homelab/backups/`.
  - GitHub push/PR flows are handled by `specialized_agents/github_client.py` — tests must pass before pushing code that triggers CI/CD.

- Quick actionable examples (copy-paste):
  - Start dashboard: `streamlit run specialized_agents/conversation_monitor.py`
  - Run agent manager API: `uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503`
  - Run full local checks: `bash setup_interceptor.sh && python3 test_interceptor.py`

- When you need to act on infra or secrets (CAUTION):
  - For system-wide changes (systemd, Fly.io, Vaultwarden), ask for explicit human approval and provide the exact command you'll run. Record backups and timestamps in `/home/homelab/backups/`.
  - Secrets automation: prefer `tools/vault/secret_store.py` (Bitwarden) — if `BW_SESSION` cannot be used, repo fallback is `tools/simple_vault/` (GPG files). Do not print secrets to logs.

If you'd like, I can: (A) prune this into an even shorter quick-reference, (B) expand instructions for adding a new agent (code + tests), or (C) create CI PR template that enforces `test_interceptor.py` before merge. Reply which one you want next.
# Copilot instructions for this repository

Purpose: make AI coding agents productive quickly in this codebase.

Quick start (3 commands)

Local development checks

Repository layout to inspect first

Fly.io / Tunnel notes (CRITICAL)

Installing `flyctl` (idempotent)
```bash
curl -L https://fly.io/install.sh | sh
export PATH="$HOME/.fly/bin:$PATH"
~/.fly/bin/flyctl version
```
Auth (choose one)

Before applying tunnel changes

