Cloudflare Tunnel — Documentação Operacional (Confluence)

Use este conteúdo para criar/atualizar a página no Confluence.

---

## Status Atual (atualizado 2026-02-12)

**Tunnel ID:** `8169b9cd-a798-4610-b3a6-ed7218f6685d`
**Host:** homelab (192.168.15.2)
**Usuário de execução:** `_rpa4all` (UID 1001) — isolado, sem sudo, sem shell interativo
**Protocolo:** QUIC (conexões registradas em GRU/GIG — Cloudflare Brasil)

### Serviços Cloudflared Ativos

| Unit systemd | Status | Usuário | Descrição |
|--------------|--------|---------|-----------|
| `cloudflared-rpa4all.service` | **active (running)** | `_rpa4all` | Tunnel principal — 8 endpoints |
| `cloudflared@dev.service` | **active (running)** | `root` | Tunnel dev — Open WebUI `:3000` |
| `cloudflared.service` | **masked (dead)** | - | Antigo, mascarado para evitar conflito |

### Endpoints Configurados

| Hostname | Path | Backend | Porta |
|----------|------|---------|-------|
| `www.rpa4all.com` | `/` | nginx | 8090 |
| `rpa4all.com` | `/` | nginx | 8090 |
| `openwebui.rpa4all.com` | `/` | Open WebUI | 3000 |
| `ide.rpa4all.com` | `/` | Code Server | 8081 |
| `grafana.rpa4all.com` | `/` | Grafana | 3001 |
| `homelab.rpa4all.com` | `/` | FastAPI (agents-api) | 8503 |
| `api.rpa4all.com` | `/agents-api/*` | Code Server | 8081 |
| `api.rpa4all.com` | `/code-runner/*` | Code Server | 8081 |

### Segurança e Permissões

| Recurso | Owner | Mode | Caminho |
|---------|-------|------|---------|
| Config do tunnel | `root:_rpa4all` | 640 | `/etc/cloudflared/config.yml` |
| Credenciais JSON | `root:_rpa4all` | 640 | `/etc/cloudflared/8169b9cd-*.json` |
| Override systemd | `root:root` | 644 | `.../cloudflared-rpa4all.service.d/override.conf` |
| Sudoers restrito | `root:root` | 440 | `/etc/sudoers.d/homelab-limited` |

**Usuário `homelab`:** removido do grupo `sudo`; acesso restrito a comandos de monitoramento via sudoers limitado:
- `journalctl -u cloudflared*` (NOPASSWD, NOEXEC)
- `systemctl status cloudflared*` (NOPASSWD, NOEXEC)
- `systemctl status resolved-check*` (NOPASSWD, NOEXEC)
- `less /var/log/cloudflared.log` (NOPASSWD, NOEXEC)

**Usuário `_rpa4all`:** sem login, sem sudo, grupos: apenas `_rpa4all`. Executa cloudflared como serviço.

### DNS — Proteção contra falhas

**Problema original (2026-02-12):** Stub resolver local (`127.0.0.53`) falhava ao resolver `protocol-v2.argotunnel.com`, causando QUIC timeouts e queda dos tunnels.

**Solução aplicada:**
1. `systemd-resolved` reconfigurado: DNS upstream `8.8.8.8`/`8.8.4.4`, fallback `1.1.1.1`/`9.9.9.9`
2. `DNSStubListener=no` — desabilitado stub para evitar recursão local
3. `resolved-check.timer` — health-check a cada 60s, reinicia `systemd-resolved` se resolução falhar
4. Script: `/usr/local/bin/check_resolved.sh`

### Recovery

- **MAC para WoL:** `d0:94:66:bb:c4:f6`
- **Em caso de lockout sudo:** usar Docker (homelab no grupo `docker`) para montar `/etc` e criar/editar sudoers
- **Rollback:** `git reflog` → `git reset --hard <commit>` → `systemctl restart <service>`

---

## Histórico de Migração

### Fase 1 — Planejamento (completado)
- [x] Inventariar serviços (8 endpoints mapeados)
- [x] Definir janela e fallback

### Fase 2 — Preparação do host (completado)
- [x] Instalar `cloudflared`
- [x] `cloudflared tunnel login`
- [x] Criar usuário `_rpa4all` dedicado

### Fase 3 — Criar e configurar túnel (completado)
- [x] `cloudflared tunnel create rpa4all-tunnel`
- [x] `/etc/cloudflared/config.yml` com 8 regras de ingress
- [x] Credenciais migradas de `/home/homelab/.cloudflared/` para `/etc/cloudflared/`

### Fase 4 — Deploy e cutover (completado)
- [x] Unit systemd habilitada (`cloudflared-rpa4all.service`)
- [x] Override `User=_rpa4all, Group=_rpa4all`
- [x] DNS apontando para CNAME do tunnel
- [x] Antigo `cloudflared.service` mascarado

### Fase 5 — Pós-migração (completado 2026-02-12)
- [x] Serviço antigo mascarado
- [x] Permissões de `homelab` restritas (sem sudo completo)
- [x] DNS resolver hardened (upstream + health-check timer)
- [x] Todos os endpoints validados (HTTP 200/401/404/405 — esperados)
- [x] Documentação atualizada (SERVER_CONFIG.md, Confluence, draw.io)

### Anexos técnicos
- Diagrama: `docs/diagrams/cloudflare_tunnel.drawio`
- Config: `tools/tunnels/`
- Recovery: `tools/homelab_recovery/`

### Checklist Confluence
- [x] Página criada e linkada no espaço de Operações
- [x] Passos de rollback documentados
- [x] Owners e contatos adicionados
