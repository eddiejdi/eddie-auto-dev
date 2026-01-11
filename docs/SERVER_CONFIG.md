# 🖥️ Configuração do Servidor - Home Lab

## ⚠️ IMPORTANTE - Usuário do Sistema

O servidor home lab (192.168.15.2) usa **APENAS** o usuário `home-lab`.

### ❌ NÃO USAR
- ~~eddie~~
- ~~root~~ (exceto quando necessário com sudo)

### ✅ USAR SEMPRE
- **Usuário:** `home-lab`
- **Home:** `/home/home-lab`
- **Projetos:** `/home/home-lab/myClaude`

---

## 📁 Estrutura de Diretórios

```
/home/home-lab/
├── myClaude/                    # Repositório principal
│   ├── btc_trading_agent/       # Agente de trading BTC
│   ├── specialized_agents/      # Agentes especializados
│   ├── eddie-copilot/           # Extensão VS Code
│   ├── gmail_data/              # Dados do Gmail
│   ├── calendar_data/           # Dados do Calendar
│   ├── whatsapp_data/           # Dados do WhatsApp
│   └── ...
├── .local/bin/                  # Binários Python (pip, uvicorn, etc)
└── .ssh/                        # Chaves SSH
```

---

## 🔐 Acesso SSH

```bash
# Conexão correta
ssh home-lab@192.168.15.2

# ERRADO - não usar
# ssh eddie@192.168.15.2
```

---

## 🔧 Serviços Systemd

Todos os serviços rodam com:
- `User=home-lab`
- `Group=home-lab`
- `WorkingDirectory=/home/home-lab/myClaude/...`

### Lista de Serviços

| Serviço | Descrição | Porta |
|---------|-----------|-------|
| `eddie-telegram-bot` | Bot Telegram | - |
| `eddie-whatsapp-bot` | Bot WhatsApp | - |
| `eddie-calendar` | Lembretes Calendar | - |
| `github-agent` | Agente GitHub | - |
| `specialized-agents` | Dashboard Streamlit | 8502 |
| `specialized-agents-api` | API dos Agentes | 8503 |
| `btc-trading-agent` | Trading Bot | - |
| `btc-trading-engine` | Engine de Trading | - |
| `btc-engine-api` | API do Engine | 8511 |
| `btc-webui-api` | API WebUI | 8510 |

### Comandos Úteis

```bash
# Ver status de um serviço
sudo systemctl status eddie-telegram-bot

# Reiniciar serviço
sudo systemctl restart eddie-telegram-bot

# Ver logs
sudo journalctl -u eddie-telegram-bot -f

# Listar todos os serviços eddie
systemctl list-units --type=service | grep eddie
systemctl list-units --type=service | grep btc
```

---

## 🔄 CI/CD

O GitHub Actions usa:
- **DEPLOY_USER:** `home-lab`
- **DEPLOY_PATH:** `/home/home-lab/myClaude`
- **DEPLOY_HOST:** `192.168.15.2`

O deploy via SSH requer:
1. Chave SSH configurada em GitHub Secrets (`DEPLOY_SSH_KEY`)
2. Chave pública adicionada em `/home/home-lab/.ssh/authorized_keys`

---

## 📝 Histórico de Mudanças

| Data | Alteração |
|------|-----------|
| 2026-01-11 | Migração de `eddie` para `home-lab` |

---

## 🚨 Lembretes

1. **NUNCA** use `/home/eddie` em arquivos de configuração
2. **SEMPRE** verifique `User=home-lab` nos arquivos .service
3. **SEMPRE** use `ssh home-lab@192.168.15.2`
4. Ao criar novos serviços, use o template em `docs/service-template.service`
