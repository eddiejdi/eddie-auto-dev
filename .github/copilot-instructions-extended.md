# Extended Copilot Instructions — Eddie Auto-Dev

This companion file contains practical, operational details that help an AI coding agent and developers debug, simulate, and deploy safely.

## Troubleshooting & logs 🔍
- Agent ping probe results: `/tmp/agent_ping_results.txt` (created by ping helpers); check this first if 'no responses' observed.
- CI artifacts: health logs are uploaded as `sre-health-logs` in GH Actions; when downloaded locally they are under `/tmp/ci-artifacts/<run>`.
- Check systemd unit logs: `journalctl -u diretor.service`, `journalctl -u coordinator.service`, `journalctl -u specialized-agents-api.service`.

## DB-backed IPC (Postgres) — practical notes 🗄️
- The in-memory bus is process-local. For cross-process delivery use `tools/agent_ipc.py` (Postgres). Set `DATABASE_URL` for services that must share requests/responses.
- Quick Postgres quickstart (dev):
  - `docker run -d --name eddie-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres`
  - Add `Environment=DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres` to systemd drop-ins for `diretor`, `coordinator`, and `specialized-agents-api` and `systemctl daemon-reload && systemctl restart <unit>`.
- Usage example (publish + poll):
```py
from tools import agent_ipc
rid = agent_ipc.publish_request('assistant','DIRETOR','Please approve','{}')
resp = agent_ipc.poll_response(rid, timeout=60)
print(resp)
```

## Common service issues & fixes 🩺
- `specialized-agents-api` fails with `ModuleNotFoundError: No module named 'paramiko'` → install: `.venv/bin/pip install paramiko` and restart service.
- Networking/tunnel failures (Open WebUI unreachable): verify `openwebui-ssh-tunnel.service` or `cloudflared` config in `site/deploy/` and file permissions (e.g., `/etc/cloudflared/config.yml`).

## Helpful scripts & how to use them ⚙️
- `tools/invoke_director.py "message"` — quick in-process publish to `DIRETOR`.
- `tools/ask_director_coordinator.py` — publishes to both Director & Coordinator (also writes to DB IPC if available).
- `tools/force_diretor_response.py` — write a fake director response to `/tmp/diretor_response.json` for local flow testing.
- `tools/monitor_diretor_response.py` and `tools/wait_for_diretor.py` — poll helpers that wait for director responses.

## CI & health-check behavioral notes ⚠️
- Infra-sensitive checks (env-sync / deploy_interceptor) were made non-fatal and now upload health artifacts so PRs do not fail outright when homelab is temporarily inaccessible.
- If you need to re-run a workflow and it says "cannot be rerun; workflow file may be broken", validate with `ci-debug.yml` (py_compile + YAML checks) and review the workflow file for syntax changes.

## Site & deploy specifics 🌐
- Site root: `site/` — includes `index.html`, `styles.css`, `script.js`, and `openwebui-config.json` (iframe embedding Open WebUI on port 3000).
- Deployment options (see `site/deploy/`):
  - `openwebui-ssh-tunnel.service` (systemd unit for reverse SSH tunnel)
  - `nginx` sample confs for reverse proxy
  - `cloudflared` configs for DNS+TLS via Cloudflare tunnel
- To enable the systemd tunnel service, create `/etc/default/openwebui-ssh-tunnel` with `REMOTE=<user@host>` then `sudo systemctl enable --now openwebui-ssh-tunnel`.

## Testing & local simulation 🧪
- Run Selenium E2E locally: `pytest tests/test_site_selenium.py` (ensure Chrome/driver available or use webdriver-manager).
- To simulate a Director approval in flows that poll DB IPC, either use `tools/consume_diretor_db_requests.py` (if `DATABASE_URL` is set) or `tools/force_diretor_response.py` for quick local tests.

## Quick commands reference 🔁
- Start services: `sudo systemctl restart diretor.service coordinator.service specialized-agents-api.service`
- Check API: `curl http://localhost:8503/status`
- Broadcast coordinator ping (API):
```bash
curl -X POST http://localhost:8503/communication/publish \
  -H 'Content-Type: application/json' \
  -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
```

---
If you want, I can fold selected sections of this extended doc back into `.github/copilot-instructions.md` (shorter) or keep it as a companion reference. Tell me which approach you prefer.