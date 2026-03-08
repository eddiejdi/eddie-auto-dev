# 🖥️ Configuração do Servidor - Home Lab

## ⚠️ IMPORTANTE - Usuários do Sistema

O servidor home lab (192.168.15.2) possui dois usuários operacionais:

### Usuário `homelab` (UID 1000) — operador geral
- **Home:** `/home/homelab`
- **Projetos:** `/home/homelab/myClaude`
- **Grupos:** `homelab adm lp cdrom dip plugdev lxd docker libvirt lpadmin scanner vboxusers`
- **Sudo:** RESTRITO — apenas monitoramento de cloudflared (via `/etc/sudoers.d/homelab-limited`)
- **Comandos sudo permitidos:**
  - `journalctl -u cloudflared*`
  - `systemctl status cloudflared*`
  - `systemctl status resolved-check*`
  - `less /var/log/cloudflared.log`
- **Flags:** `NOPASSWD`, `NOEXEC`, `!setenv`

### Usuário `_rpa4all` (UID 1001) — serviço Cloudflare Tunnel
- **Criado em:** 2026-02-12
- **Propósito:** executar exclusivamente o `cloudflared-rpa4all.service`
- **Grupos:** `_rpa4all` (isolado)
- **Sem shell interativo**, sem sudo, sem acesso SSH direto
- **Credenciais:** `/etc/cloudflared/*.json` (owner `root:_rpa4all`, mode 640)

### ❌ NÃO USAR
- ~~shared~~ (não existe)
- ~~home-lab~~ (com hífen - ERRADO!)
- ~~root~~ (apenas via Docker escape em emergências — ver Recovery)

---

## 📁 Estrutura de Diretórios

/home/homelab/
├── myClaude/                    # Repositório principal
│   ├── btc_trading_agent/       # Agente de trading BTC
│   ├── specialized_agents/      # Agentes especializados
│   ├── shared-copilot/           # Extensão VS Code
│   ├── gmail_data/              # Dados do Gmail
│   ├── calendar_data/           # Dados do Calendar
│   ├── whatsapp_data/           # Dados do WhatsApp
│   └── ...
├── .local/bin/                  # Binários Python (pip, uvicorn, etc)
└── .ssh/                        # Chaves SSH
---

## 🔐 Acesso SSH

```bash
# Conexão correta
ssh homelab@192.168.15.2

# ERRADO - não usar
# ssh shared@192.168.15.2
---

## 🔧 Serviços Systemd

Todos os serviços rodam com:
- `User=homelab`
- `Group=homelab`
- `WorkingDirectory=/home/homelab/myClaude/...`

### Lista de Serviços

| Serviço | Descrição | Porta | Usuário |
|---------|-----------|-------|---------|
| `shared-telegram-bot` | Bot Telegram | - | homelab |
| `shared-whatsapp-bot` | Bot WhatsApp | - | homelab |
| `shared-calendar` | Lembretes Calendar | - | homelab |
| `github-agent` | Agente GitHub | - | homelab |
| `specialized-agents` | Dashboard Streamlit | 8502 | homelab |
| `specialized-agents-api` | API dos Agentes | 8503 | homelab |
| `btc-trading-agent` | Trading Bot | - | homelab |
| `btc-trading-engine` | Engine de Trading | - | homelab |
| `btc-engine-api` | API do Engine | 8511 | homelab |
| `btc-webui-api` | API WebUI | 8510 | homelab |
| `cloudflared-rpa4all` | Cloudflare Tunnel principal | - | **_rpa4all** |
| `cloudflared@dev` | Cloudflare Tunnel dev (Open WebUI) | - | root |
| `cloudflared.service` | **MASCARADO** (antigo, conflitava) | - | - |
| `resolved-check.timer` | Health-check DNS a cada 60s | - | root |

### Comandos Úteis

```bash
# Ver status de um serviço
sudo systemctl status shared-telegram-bot

# Reiniciar serviço
sudo systemctl restart shared-telegram-bot

# Ver logs
sudo journalctl -u shared-telegram-bot -f

# Listar todos os serviços shared
systemctl list-units --type=service | grep shared
systemctl list-units --type=service | grep btc
---

## 🔄 CI/CD

O GitHub Actions usa:
- **DEPLOY_USER:** `homelab`
- **DEPLOY_PATH:** `/home/homelab/myClaude`
- **DEPLOY_HOST:** `192.168.15.2`

O deploy via SSH requer:
1. Chave SSH configurada em GitHub Secrets (`DEPLOY_SSH_KEY`)
2. Chave pública adicionada em `/home/homelab/.ssh/authorized_keys`

---

## 📝 Histórico de Mudanças

| Data | Alteração |
|------|-----------|
| 2026-02-12 | Criado usuário `_rpa4all` para cloudflared tunnel isolado |
| 2026-02-12 | Removido `homelab` do grupo `sudo`; criado `/etc/sudoers.d/homelab-limited` (monitoramento apenas) |
| 2026-02-12 | Mascarado `cloudflared.service` antigo; ativo: `cloudflared-rpa4all.service` + `cloudflared@dev.service` |
| 2026-02-12 | DNS reconfigurado: upstream 8.8.8.8/8.8.4.4, stub desabilitado, `resolved-check.timer` a cada 60s |
| 2026-02-12 | Credenciais movidas para `/etc/cloudflared/` com owner `root:_rpa4all` mode 640 |
| 2026-02-12 | MAC do homelab registrado: `d0:94:66:bb:c4:f6` (WoL) |
| 2026-01-11 | Migração de `shared` para `homelab` |

---

## 🚨 Lembretes

1. **NUNCA** use `/home/shared` em arquivos de configuração
2. **SEMPRE** verifique `User=homelab` nos arquivos .service (exceto cloudflared → `_rpa4all`)
3. **SEMPRE** use `ssh homelab@192.168.15.2`
4. Ao criar novos serviços, use o template em `docs/service-template.service`
5. **NUNCA** remova `homelab` do grupo `sudo` sem antes criar o sudoers restrito
6. Em caso de lockout de sudo, use Docker (homelab está no grupo `docker`) para montar `/etc` e criar sudoers
7. **WoL MAC:** `d0:94:66:bb:c4:f6` — usar `wakeonlan d0:94:66:bb:c4:f6` se servidor offline

---

## 🌐 Cloudflare Tunnel — Endpoints

| Endpoint | Backend local | Serviço systemd |
|----------|--------------|-----------------|
| `www.rpa4all.com` / `rpa4all.com` | `127.0.0.1:8090` (nginx) | `cloudflared-rpa4all` |
| `openwebui.rpa4all.com` | `127.0.0.1:3000` (Open WebUI) | `cloudflared-rpa4all` |
| `ide.rpa4all.com` | `127.0.0.1:8081` (Code Server) | `cloudflared-rpa4all` |
| `grafana.rpa4all.com` | `127.0.0.1:3001` (Grafana) | `cloudflared-rpa4all` |
| `homelab.rpa4all.com` | `127.0.0.1:8503` (FastAPI) | `cloudflared-rpa4all` |
| `api.rpa4all.com/agents-api/*` | `127.0.0.1:8081` | `cloudflared-rpa4all` |
| `api.rpa4all.com/code-runner/*` | `127.0.0.1:8081` | `cloudflared-rpa4all` |

### DNS
- `systemd-resolved` com upstream `8.8.8.8`/`8.8.4.4`, fallback `1.1.1.1`/`9.9.9.9`
- Stub listener desabilitado (`DNSStubListener=no`)
- Health-check automático: `resolved-check.timer` (60s) verifica resolução de `protocol-v2.argotunnel.com`

### Permissões do Tunnel
- Config: `/etc/cloudflared/config.yml` — `root:_rpa4all` 640
- Credenciais: `/etc/cloudflared/8169b9cd-*.json` — `root:_rpa4all` 640
- Override: `/etc/systemd/system/cloudflared-rpa4all.service.d/override.conf` — `User=_rpa4all, Group=_rpa4all`
