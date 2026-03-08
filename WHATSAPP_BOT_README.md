# 📱 Shared WhatsApp Bot

Bot de WhatsApp integrado com IA (Ollama/OpenWebUI) para o número **5511981193899**.

## 🏗️ Arquitetura

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   WhatsApp      │────▶│      WAHA       │────▶│  WhatsApp Bot   │
│   (Celular)     │◀────│  (Docker API)   │◀────│    (Python)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │     Ollama      │
                                                │   (IA Local)    │
                                                └─────────────────┘
## 📁 Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `whatsapp_bot.py` | Bot principal com integração IA |
| `whatsapp_manager.py` | Interface web de gerenciamento (Streamlit) |
| `install_whatsapp_bot.sh` | Script de instalação automática |
| `shared-whatsapp-bot.service` | Serviço systemd |
| `whatsapp_data/` | Diretório de dados e sessões |

## 🚀 Instalação Rápida

### 1. Executar o instalador

```bash
cd ~/myClaude
chmod +x install_whatsapp_bot.sh
./install_whatsapp_bot.sh
### 2. Conectar o WhatsApp

Após a instalação, acesse o QR Code:

```bash
# Opção 1: Via navegador
http://localhost:3000/api/sessions/shared/auth/qr

# Opção 2: Via logs do Docker
docker logs -f waha

# Opção 3: Via interface Streamlit
streamlit run whatsapp_manager.py --server.port 5002
# Acesse: http://localhost:5002
**Escaneie o QR Code** com o WhatsApp do número 5511981193899.

### 3. Iniciar o Bot

```bash
# Manualmente
source .env.whatsapp
python3 whatsapp_bot.py

# Ou via systemd
sudo cp shared-whatsapp-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shared-whatsapp-bot
sudo systemctl start shared-whatsapp-bot
## 📝 Configuração

### Variáveis de Ambiente (.env.whatsapp)

```bash
# WhatsApp
WHATSAPP_NUMBER=5511981193899
WAHA_URL=http://localhost:3004
WAHA_API_KEY=

# IA
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=shared-coder
OPENWEBUI_HOST=http://192.168.15.2:3000

# Admin (números separados por vírgula)
ADMIN_NUMBERS=5511981193899
### Configuração do WAHA Webhook

O WAHA envia eventos para `http://localhost:5001/webhook`. O bot precisa estar rodando para receber mensagens.

## 💬 Comandos Disponíveis

### Comandos Básicos (todos os usuários)

| Comando | Descrição |
|---------|-----------|
| `/help` ou `ajuda` | Mostra ajuda |
| `/ping` | Verifica se o bot está online |
| `/limpar` | Limpa histórico da conversa |
| `/perfil <nome>` | Muda perfil de IA |
| `/status` | Mostra status do bot |
| `/modelos` | Lista modelos disponíveis |

### Perfis de IA

| Perfil | Aliases | Uso |
|--------|---------|-----|
| `coder` | code, dev, programar | Programação |
| `homelab` | home, server, infra | Servidores |
| `assistant` | pessoal, msg, criativo | Geral |
| `fast` | rapido, quick | Respostas rápidas |
| `advanced` | avancado, complex | Análises complexas |
| `github` | git, repo | Git/GitHub |

### Comandos de Admin

| Comando | Descrição |
|---------|-----------|
| `/modelo <nome>` | Altera modelo de IA |
| `/stats` | Mostra estatísticas |

## 🔧 Gerenciamento

### Interface Web (Streamlit)

```bash
pip install streamlit httpx qrcode pillow
streamlit run whatsapp_manager.py --server.port 5002
Acesse: http://localhost:5002

Funcionalidades:
- 📊 Ver status da conexão
- 📷 Exibir/escanear QR Code
- 💬 Enviar mensagens de teste
- 📋 Listar conversas

### Comandos Docker (WAHA)

```bash
# Ver logs
docker logs -f waha

# Reiniciar
docker restart waha

# Parar
docker stop waha

# Ver status
docker ps | grep waha

# Recriar container
docker rm -f waha
./install_whatsapp_bot.sh
### Systemd (Bot Python)

```bash
# Status
sudo systemctl status shared-whatsapp-bot

# Iniciar
sudo systemctl start shared-whatsapp-bot

# Parar
sudo systemctl stop shared-whatsapp-bot

# Logs
journalctl -u shared-whatsapp-bot -f

# Ou arquivo de log
tail -f /tmp/whatsapp_bot.log
## 🔌 API Endpoints

O bot expõe os seguintes endpoints:

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/webhook` | POST | Recebe eventos do WAHA |
| `/health` | GET | Health check |
| `/status` | GET | Status do bot |
| `/qr` | GET | QR Code atual |

## 📊 Banco de Dados

O bot usa SQLite para armazenar conversas:
OLLAMA_HOST=http://${HOMELAB_HOST}:11434
OPENWEBUI_HOST=http://${HOMELAB_HOST}:3000
whatsapp_data/
├── conversations.db    # Banco de dados
└── sessions/          # Sessões WAHA
### Tabelas

**messages**
- id, chat_id, sender, role, content, timestamp, is_group

**sessions**
- chat_id, profile, last_activity

## 🔍 Solução de Problemas

### WAHA não inicia

```bash
# Verificar Docker
docker ps -a
docker logs waha

# Reiniciar
docker restart waha
### QR Code não aparece

```bash
# Ver logs do WAHA
docker logs -f waha | grep -i qr

# Reiniciar sessão
curl -X POST http://localhost:3000/api/sessions/shared/restart
### Bot não responde

```bash
# Verificar se está rodando
ps aux | grep whatsapp_bot

# Ver logs
tail -f /tmp/whatsapp_bot.log

# Testar Ollama
curl http://192.168.15.2:11434/api/tags
### Webhook não recebe mensagens

```bash
# Testar webhook manualmente
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{"event":"message","payload":{"body":"teste"}}'

# Verificar configuração do WAHA
docker exec waha cat /app/.sessions/shared/config.json
## 🛡️ Segurança

- O bot só executa comandos de admin para números na lista `ADMIN_NUMBERS`
- Dados são armazenados localmente
- Não compartilhe o arquivo `.env.whatsapp`
- Tokens e chaves são sensíveis

## 📚 Tecnologias Utilizadas

- **WAHA** - WhatsApp HTTP API (Docker)
- **Python 3** - Linguagem principal
- **aiohttp** - Servidor webhook async
- **httpx** - Cliente HTTP async
- **SQLite** - Banco de dados local
- **Ollama** - IA local
- **Streamlit** - Interface web

## 🔗 Links Úteis

- [WAHA Documentation](https://waha.devlike.pro/)
- [WAHA GitHub](https://github.com/devlikeapro/waha)
- [Ollama](https://ollama.ai/)

## ⚠️ Disclaimer

Este projeto usa APIs não-oficiais do WhatsApp. Use por sua conta e risco. O WhatsApp pode bloquear números que usam automação. Para uso comercial, considere a API oficial do WhatsApp Business.

---

**Número configurado:** 5511981193899  
**Versão:** 1.0.0  
**Última atualização:** Janeiro 2026
