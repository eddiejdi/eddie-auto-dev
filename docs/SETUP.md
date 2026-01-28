# ⚙️ Guia de Configuração - Eddie Auto-Dev System

## Pré-requisitos

### Sistema Operacional
- Ubuntu 20.04+ ou derivados
- WSL2 no Windows (testado)

### Software Necessário
```bash
# Python 3.11+
python3 --version

# Docker
docker --version

# Git
git --version

# pip
pip3 --version
```

---

## Instalação Passo a Passo

### 1. Clone o Repositório

```bash
cd ~
git clone https://github.com/eddiejdi/myClaude.git
cd myClaude
```

### 2. Crie o Ambiente Virtual

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 3. Instale Dependências

```bash
# Dependências principais
pip install httpx asyncio python-dotenv

# Para a API
pip install fastapi uvicorn pydantic python-multipart

# Para RAG
pip install chromadb sentence-transformers

# Para busca web
pip install duckduckgo-search beautifulsoup4
```

### 4. Configure Variáveis de Ambiente

Crie o arquivo `.env`:

```bash
cat > .env << 'EOF'
# ========== TELEGRAM ==========
TELEGRAM_BOT_TOKEN=<store in tools/simple_vault/secrets and encrypt; do not commit plaintext>
ADMIN_CHAT_ID=seu_chat_id_aqui

# ========== OLLAMA ==========
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=eddie-coder

# ========== GITHUB ==========
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx

# ========== API ==========
AGENTS_API=http://localhost:8503
EOF
```

### 5. Configure o Telegram Bot

1. Fale com @BotFather no Telegram
2. Crie um novo bot: `/newbot`
3. Copie o token fornecido
4. Obtenha seu Chat ID:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```

### 6. Configure o Ollama

```bash
# No servidor homelab (192.168.15.2)
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Baixar modelo
ollama pull qwen2.5-coder:7b

# Criar modelo customizado
ollama create eddie-coder -f eddie-homelab.Modelfile
```

**Exemplo de Modelfile:**
```dockerfile
FROM qwen2.5-coder:7b

SYSTEM """
Você é Eddie, um assistente de programação especializado.
Você ajuda com:
- Desenvolvimento de software
- Debugging e correção de erros
- Arquitetura de sistemas
- DevOps e infraestrutura

Sempre responda em português brasileiro de forma clara e objetiva.
"""

PARAMETER temperature 0.7
PARAMETER num_ctx 8192
```

### 7. Configure o GitHub Token

1. Acesse GitHub → Settings → Developer settings → Personal access tokens
2. Crie um token com permissões:
   - `repo` (full control)
   - `workflow` (se usar Actions)
3. Adicione ao `.env`

---

## Configuração dos Serviços

### Systemd - Bot Telegram

```bash
sudo tee /etc/systemd/system/eddie-telegram-bot.service << 'EOF'
[Unit]
Description=Eddie Telegram Bot
After=network.target

[Service]
Type=simple
User=eddie
WorkingDirectory=/home/homelab/myClaude
Environment=PATH=/home/homelab/myClaude/venv/bin:/usr/bin
ExecStart=/home/homelab/myClaude/venv/bin/python3 telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable eddie-telegram-bot
sudo systemctl start eddie-telegram-bot
```

### Systemd - Agents API

```bash
sudo tee /etc/systemd/system/specialized-agents.service << 'EOF'
[Unit]
Description=Specialized Agents API
After=network.target docker.service

[Service]
Type=simple
User=eddie
WorkingDirectory=/home/homelab/myClaude/specialized_agents
Environment=PATH=/home/homelab/.local/bin:/usr/bin
ExecStart=/home/homelab/.local/bin/uvicorn api:app --host 0.0.0.0 --port 8503
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable specialized-agents
sudo systemctl start specialized-agents
```

---

## Configuração do Docker

### Instalação

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### Preparar Imagens Base

```bash
# Python
docker pull python:3.12-slim

# Node.js
docker pull node:20-slim

# Go
docker pull golang:1.22-alpine

# Rust
docker pull rust:1.75-slim

# Java
docker pull eclipse-temurin:21-jdk

# .NET
docker pull mcr.microsoft.com/dotnet/sdk:8.0

# PHP
docker pull php:8.3-cli
```

---

## Configuração do RAG (ChromaDB)

### Diretório de Dados

```bash
mkdir -p ~/myClaude/chroma_db
mkdir -p ~/myClaude/agent_rag
```

### Testar ChromaDB

```python
import chromadb

# Inicializar cliente persistente
client = chromadb.PersistentClient(path="./chroma_db")

# Criar coleção de teste
collection = client.get_or_create_collection("test")

# Adicionar documento
collection.add(
    documents=["Exemplo de código Python"],
    metadatas=[{"language": "python"}],
    ids=["test1"]
)

# Buscar
results = collection.query(
    query_texts=["Python"],
    n_results=1
)
print(results)
```

---

## Configuração de Rede

### Firewall (ufw)

```bash
# Permitir porta da API
sudo ufw allow 8503/tcp

# Se Ollama estiver em outra máquina
sudo ufw allow from 192.168.15.0/24 to any port 11434
```

### Proxy Reverso (Nginx) - Opcional

```nginx
# /etc/nginx/sites-available/eddie-api
server {
    listen 80;
    server_name eddie.local;
    
    location / {
        proxy_pass http://127.0.0.1:8503;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## Verificação da Instalação

### 1. Testar Ollama

```bash
curl http://192.168.15.2:11434/api/generate \
  -d '{"model": "eddie-coder", "prompt": "Olá", "stream": false}'
```

### 2. Testar API

```bash
# Health check
curl http://localhost:8503/health

# Listar agentes
curl http://localhost:8503/agents
```

### 3. Testar Bot

```bash
# Ver status
systemctl status eddie-telegram-bot

# Ver logs
journalctl -u eddie-telegram-bot -f
```

### 4. Testar RAG

```bash
curl -X POST http://localhost:8503/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python FastAPI", "n_results": 3}'
```

---

## Configurações Avançadas

### Tuning do Modelo LLM

```bash
# Ajustar parâmetros do Ollama
curl http://192.168.15.2:11434/api/generate \
  -d '{
    "model": "eddie-coder",
    "prompt": "...",
    "options": {
      "temperature": 0.7,
      "top_p": 0.9,
      "top_k": 40,
      "num_ctx": 8192,
      "repeat_penalty": 1.1
    }
  }'
```

### Limites de Recursos Docker

```yaml
# docker-compose.yml para agentes
version: '3.8'
services:
  python-agent:
    image: python:3.12-slim
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Backup Automático

```bash
# Cron job para backup
crontab -e

# Adicionar:
0 2 * * * /home/homelab/myClaude/scripts/backup.sh
```

**backup.sh:**
```bash
#!/bin/bash
BACKUP_DIR="/home/homelab/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup ChromaDB
cp -r /home/homelab/myClaude/chroma_db $BACKUP_DIR/

# Backup projetos
tar -czf $BACKUP_DIR/projects.tar.gz /home/homelab/myClaude/projects/

# Limpar backups antigos (30 dias)
find /home/homelab/backups -type d -mtime +30 -exec rm -rf {} \;
```

---

## Logs e Monitoramento

### Logs do Sistema

```bash
# Bot Telegram
journalctl -u eddie-telegram-bot -f

# API Agentes
journalctl -u specialized-agents -f

# Ollama (no servidor)
journalctl -u ollama -f
```

### Monitoramento de Recursos

```bash
# Uso de CPU/RAM
htop

# Containers Docker
docker stats

# Espaço em disco
df -h
du -sh ~/myClaude/*
```

### Alertas (Opcional)

```python
# Script de alerta
import httpx

async def send_alert(message: str):
    """Envia alerta para Telegram"""
    await httpx.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_CHAT_ID,
            "text": f"⚠️ ALERTA: {message}"
        }
    )
```

---

## Solução de Problemas de Configuração

### Bot não inicia

```bash
# Verificar variáveis de ambiente
cat ~/.env | grep TELEGRAM

# Testar token
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Ver logs detalhados
journalctl -u eddie-telegram-bot -n 100 --no-pager
```

### API não responde

```bash
# Verificar porta
lsof -i :8503

# Reiniciar serviço
sudo systemctl restart specialized-agents

# Testar manualmente
cd ~/myClaude/specialized_agents
uvicorn api:app --host 0.0.0.0 --port 8503
```

### Ollama não conecta

```bash
# Testar conectividade
ping 192.168.15.2
curl http://192.168.15.2:11434/api/tags

# Verificar firewall
sudo ufw status

# Ver logs Ollama
ssh homelab@192.168.15.2 "journalctl -u ollama -n 50"
```

### Docker sem permissão

```bash
# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Relogar ou:
newgrp docker

# Testar
docker ps
```
