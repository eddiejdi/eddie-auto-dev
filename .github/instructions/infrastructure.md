---
applyTo: "**/*homelab*,**/*docker*,**/systemd/**,**/*.service,**/*.conf,**/*deploy*,**/*ssh*,**/*ltfs*,**/*tape*,**/*nas*"
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

## NAS LTFS (192.168.15.4) — Tape HP LTO-6

### Dispositivos
- Drive: `/dev/sg0`, `/dev/st0`, `/dev/nst0` — HP Ultrium 6-SCSI, FW J5SW, Serial HUJ5485716
- FC HBA: host7, PCI `0000:01:00.1`, 8 Gbit
- Mount: `/mnt/tape/lto6` → bind `/run/ltfs-export/lto6` → bind `/srv/nextcloud/external/LTO`
- Serviço: `ltfs-lto6.service`, wrapper `/usr/local/sbin/ltfs-fc-stable-start`

### Checklist diagnóstico rápido pós-crash (OBRIGATÓRIO antes de qualquer ltfsck)
```bash
# 1. Drive SCSI OK?
sg_inq /dev/sg0 | grep -E "Vendor|Product"

# 2. Se sg_inq falha: reset LIP
echo "1" > /sys/class/fc_host/host7/issue_lip && sleep 5

# 3. Fita carregada e na posição correta?
mt -f /dev/nst0 status | head -8

# 4. CRÍTICO: Partição de dados vazia? (se remaining==maximum → pode reformatar sem perda)
sg_logs /dev/sg0 -p 0x31 | grep -E "Main.*remaining|Main.*maximum"

# 5. TapeAlert (algum flag setado = problema real de mídia)
sg_logs /dev/sg0 -p 0x2e | grep ": 1"

# 6. Tentar recuperação
ltfsck -f /dev/sg0
```

### LOCATE -20301 "Recorded Entity Not Found"
- **CAUSA**: crash + kill forçado corrompeu BOT markers (servo tracks)
- **NÃO TENTE**: limpeza física (não resolve), ltfsck -z (também falha com -20301), retension
- **SOLUÇÃO ÚNICA**: reformatar
  ```bash
  systemctl stop ltfs-lto6; pkill -9 ltfs
  mkltfs --force --device=/dev/sg0 --tape-serial=HUJ548   # ← EXATAMENTE 6 chars
  systemctl reset-failed ltfs-lto6 && systemctl start ltfs-lto6
  ```
- Serial deve ter 6 chars: use `HUJ548` (não `HUJ5485716`)

### Ejeção bloqueada por PREVENT MEDIUM REMOVAL
```bash
sg_raw /dev/sg0 1e 00 00 00 00 00  # ALLOW MEDIUM REMOVAL
sg_start --eject /dev/sg0
# alternativa: mt -f /dev/st0 offline
```

### Bind mounts — restaurar manualmente se necessário
```bash
findmnt /mnt/tape/lto6                                              # LTFS base
mount --bind /mnt/tape/lto6 /run/ltfs-export/lto6                  # export
mount --bind /run/ltfs-export/lto6 /srv/nextcloud/external/LTO     # nextcloud
```
O wrapper `/usr/local/sbin/ltfs-fc-stable-start` recria automaticamente no boot.
