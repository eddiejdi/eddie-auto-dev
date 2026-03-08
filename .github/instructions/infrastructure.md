---
applyTo: "**/*homelab*,**/*docker*,**/systemd/**,**/*.service,**/*.conf,**/*deploy*,**/*ssh*"
---

# Regras de Infraestrutura & Homelab — Shared Auto-Dev

## ⛔ Serviços críticos — NUNCA reiniciar sem confirmação
**Incidente real (2026-03-02):** restart de sshd sem confirmação → servidor inacessível → intervenção física.

### EXIGEM confirmação antes de restart/stop:
- `ssh` / `sshd`, `pihole-FTL`, `docker`, `networking` / `systemd-networkd`, `ufw` / `iptables`, `systemd-resolved`

### PODEM ser reiniciados sem pedir:
- `ollama*`, `btc-trading-agent`, `btc-prometheus-exporter`, `specialized-agents-api`, `shared-telegram-bot`, `grafana`, `prometheus`, warmup services, exporters, cloudflared

### SSH safety:
1. NUNCA modificar `/etc/ssh/sshd_config*` e reiniciar no mesmo passo
2. Sempre: (a) modificar, (b) `sudo sshd -t`, (c) **pedir confirmação**, (d) reiniciar
3. Testar em porta alternativa: `sudo sshd -p 2222`

## Homelab Agent
- SSH: `HOMELAB_HOST=192.168.15.2`, `HOMELAB_USER=homelab`, `HOMELAB_SSH_KEY=~/.ssh/id_rsa`
- API: porta 8503 → `/homelab/execute`, `/homelab/server-health`, `/homelab/docker/ps`
- Audit: `DATA_DIR/homelab_audit.jsonl`
- Módulos: `specialized_agents/homelab_agent.py` + `homelab_routes.py`

## Containers Docker (14 ativos)
| Container | Porta(s) | Função |
|-----------|----------|--------|
| shared-postgres | 5433 | Trading/IPC DB |
| grafana | 127.0.0.1:3002 | Dashboards |
| prometheus | 127.0.0.1:9090 | Métricas |
| open-webui | 3000 | LLM UI |
| pihole | 53,8053 | DNS/Ad-block |
| mailserver | 25,143,465,587,993 | Email @rpa4all.com |
| authentik-server | 9000,9443 | SSO/OAuth2 |
| nextcloud | 8880 | Cloud privada |

## Email Server (@rpa4all.com)
- Hostname: `mail.rpa4all.com`
- Compose: `/mnt/raid1/docker-mailserver/docker-compose.yml`
- Setup: `bash /mnt/raid1/docker-mailserver/setup.sh {install|account|dkim|cert|start|stop|status|dns}`

## Authentik SSO
- URL: `https://auth.rpa4all.com`
- OAuth2: Grafana, Nextcloud, OpenWebUI
- WireGuard: `wg0`, `10.66.66.0/24`
- Cloudflare Tunnel: `rpa4all-tunnel`
