# Extended Copilot Instructions — Shared Auto-Dev

This companion file contains practical, operational details that help an AI coding agent and developers debug, simulate, and deploy safely.

## Troubleshooting & logs 🔍
- Agent ping probe results: `/tmp/agent_ping_results.txt` (created by ping helpers); check this first if 'no responses' observed.
- CI artifacts: health logs are uploaded as `sre-health-logs` in GH Actions; when downloaded locally they are under `/tmp/ci-artifacts/<run>`.
- Check systemd unit logs: `journalctl -u diretor.service`, `journalctl -u coordinator.service`, `journalctl -u specialized-agents-api.service`.

## DB-backed IPC (Postgres) — practical notes 🗄️
- The in-memory bus is process-local. For cross-process delivery use `tools/agent_ipc.py` (Postgres). Set `DATABASE_URL` for services that must share requests/responses.
- Quick Postgres quickstart (dev):
  - `docker run -d --name shared-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres`
  - Add `Environment=DATABASE_URL=postgresql://postgres:shared_memory_2026@localhost:5432/postgres` to systemd drop-ins for `diretor`, `coordinator`, and `specialized-agents-api` and `systemctl daemon-reload && systemctl restart <unit>`.
- Usage example (publish + poll):
```py
from tools import agent_ipc
rid = agent_ipc.publish_request('assistant','DIRETOR','Please approve','{}')
resp = agent_ipc.poll_response(rid, timeout=60)
print(resp)
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
## 🖥️ Homelab Agent — Referência operacional

### Arquitetura
O `HomelabAgent` (singleton via `get_homelab_agent()`) abre conexão SSH com paramiko ao homelab (`192.168.15.2`). Implementa 3 camadas de segurança:
1. **IP validation** — só IPs RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) e loopback podem acessar.
2. **Command whitelist** — regex por categoria (`SYSTEM_INFO`, `DOCKER`, `SYSTEMD`, `NETWORK`, `FILES`, `PROCESS`, `LOGS`, `PACKAGE`). Padrões customizáveis via `add_custom_pattern()`.
3. **Blocklist explícita** — rejeita `rm -rf /`, `mkfs`, `dd if=`, `:(){`, `chmod 777 /`, `shutdown`, `reboot`, etc.

### Arquivos relevantes
| Arquivo | Descrição |
|---------|-----------|
| `specialized_agents/homelab_agent.py` | Agente principal: SSH, segurança, audit |
| `specialized_agents/homelab_routes.py` | Rotas FastAPI `/homelab/*` |
| `tests/test_homelab_agent.py` | 28 testes unitários |
| `shared-copilot/src/homelabAgentClient.ts` | Cliente TypeScript para extensão VS Code |
| `docs/HOMELAB_AGENT.md` | Documentação completa |

### Variáveis de ambiente & config
```bash
HOMELAB_HOST=192.168.15.2     # IP do servidor homelab (default)
HOMELAB_USER=homelab           # Usuário SSH
HOMELAB_SSH_KEY=~/.ssh/id_rsa  # Chave privada SSH
DATA_DIR=./data                # Diretório para audit log (homelab_audit.jsonl)
```

### Endpoints da API (`/homelab/*`, porta 8503)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/homelab/health` | Health check do agente |
| GET | `/homelab/server-health` | Saúde completa do servidor (CPU, RAM, disco) |
| POST | `/homelab/execute` | Executar comando arbitrário (validado) |
| POST | `/homelab/validate-command` | Validar se comando é permitido |
| GET | `/homelab/docker/ps` | Listar containers Docker |
| POST | `/homelab/docker/logs` | Logs de container específico |
| GET | `/homelab/docker/stats` | Estatísticas dos containers |
| POST | `/homelab/docker/restart` | Reiniciar container |
| POST | `/homelab/systemd/status` | Status de serviço systemd |
| POST | `/homelab/systemd/restart` | Reiniciar serviço systemd |
| GET | `/homelab/systemd/list` | Listar serviços ativos |
| POST | `/homelab/systemd/logs` | Logs de serviço via journalctl |
| GET | `/homelab/system/disk` | Uso de disco |
| GET | `/homelab/system/memory` | Uso de memória |
| GET | `/homelab/system/cpu` | Informações de CPU |
| GET | `/homelab/system/network` | Interfaces de rede |
| GET | `/homelab/system/ports` | Portas abertas |
| GET | `/homelab/audit` | Últimas entradas do audit log |
| GET | `/homelab/allowed-commands` | Padrões permitidos por categoria |
| POST | `/homelab/allowed-commands/add` | Adicionar padrão customizado |

### Troubleshooting Homelab Agent
- **SSH connection refused**: Verificar se `sshd` está rodando no homelab e que a chave está em `~/.ssh/id_rsa`.
- **Command blocked**: Usar `POST /homelab/validate-command` para testar se o comando é permitido. Se legítimo, adicionar via `POST /homelab/allowed-commands/add`.
- **403 Forbidden**: A requisição veio de IP externo (não RFC 1918). Verificar headers `X-Forwarded-For` se usando reverse proxy.
- **paramiko não instalado**: `.venv/bin/pip install paramiko` e reiniciar serviço.
- **Audit log**: `cat $DATA_DIR/homelab_audit.jsonl | jq .` para inspecionar histórico de comandos.

### VS Code Extension — Comandos do Homelab
7 comandos registrados no Command Palette (`Ctrl+Shift+P`):
| Comando | ID | Descrição |
|---------|----|-----------|
| Homelab: Executar Comando | `shared-copilot.homelabExecute` | Executa comando arbitrário via input box |
| Homelab: Server Health | `shared-copilot.homelabHealth` | Exibe saúde do servidor |
| Homelab: Docker PS | `shared-copilot.homelabDockerPs` | Lista containers Docker |
| Homelab: Docker Logs | `shared-copilot.homelabDockerLogs` | Logs de container (input: nome) |
| Homelab: Systemd Status | `shared-copilot.homelabSystemdStatus` | Status de serviço (input: nome) |
| Homelab: Systemd Restart | `shared-copilot.homelabSystemdRestart` | Restart de serviço (input: nome) |
| Homelab: System Logs | `shared-copilot.homelabLogs` | Logs recentes do sistema |

Config necessária em `settings.json`:
```json
{
    "shared-copilot.agentsApiUrl": "http://localhost:8503"
}
```

---
If you want, I can fold selected sections of this extended doc back into `.github/copilot-instructions.md` (shorter) or keep it as a companion reference. Tell me which approach you prefer.