# 🔧 Troubleshooting Guide - Eddie Auto-Dev System

## Diagnóstico Rápido

### Verificar Status Geral

```bash
# Script de diagnóstico completo
#!/bin/bash

echo "=== Eddie Auto-Dev System - Diagnóstico ==="
echo ""

echo "1. Bot Telegram:"
pgrep -af telegram_bot && echo "✅ Rodando" || echo "❌ Parado"

echo ""
echo "2. API Agentes:"
curl -s http://localhost:8503/health > /dev/null 2>&1 && echo "✅ Rodando" || echo "❌ Parado"

echo ""
echo "3. Ollama:"
curl -s http://192.168.15.2:11434/api/tags > /dev/null 2>&1 && echo "✅ Conectado" || echo "❌ Desconectado"

echo ""
echo "4. Docker:"
docker ps > /dev/null 2>&1 && echo "✅ Disponível" || echo "❌ Erro"

echo ""
echo "5. Portas em uso:"
lsof -i :8503 | grep LISTEN
---

## Problemas Comuns

### 1. Bot Telegram Não Responde

#### Sintomas
- Mensagens enviadas não são respondidas
- Bot aparece offline no Telegram

#### Causas e Soluções

**Causa 1: Bot não está rodando**
```bash
# Verificar
pgrep -af telegram_bot

# Solução: Iniciar o bot
python3 /home/homelab/myClaude/telegram_bot.py &
# ou
sudo systemctl start eddie-telegram-bot
**Causa 2: Token inválido**
```bash
# Testar token
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Se retornar erro 401, o token está errado
# Gerar novo token com @BotFather
**Causa 3: Bot ignorando mensagens antigas**
```bash
# O bot ignora mensagens com mais de 60 segundos
# Isso é esperado para evitar processar mensagens antigas

# Verificar nos logs
journalctl -u eddie-telegram-bot -n 50 | grep -i "ignorando"
**Causa 4: Erro de conexão com Ollama**
```bash
# Verificar logs
journalctl -u eddie-telegram-bot -n 50 | grep -i "ollama\|erro"

# Testar conexão
curl http://192.168.15.2:11434/api/tags
---

### 2. API Retorna Erro 500

#### Sintomas
- Requests retornam Internal Server Error
- Criação de projetos falha

#### Causas e Soluções

**Causa 1: Manager não inicializado**
```bash
# Reiniciar API
sudo systemctl restart specialized-agents

# Verificar logs de inicialização
journalctl -u specialized-agents -n 100 | grep -i "startup\|error"
**Causa 2: Dependências faltando**
```bash
# Instalar dependências
pip install fastapi uvicorn pydantic chromadb httpx

# Verificar importações
python3 -c "from specialized_agents import api"
**Causa 3: Porta em uso**
```bash
# Verificar quem está usando a porta
lsof -i :8503

# Matar processo se necessário
kill -9 <PID>

# Reiniciar API
sudo systemctl restart specialized-agents
---

### 3. Ollama Não Conecta

#### Sintomas
- Erro de conexão refused
- Timeout nas requisições

#### Causas e Soluções

**Causa 1: Ollama não está rodando**
```bash
# No servidor Ollama (192.168.15.2)
systemctl status ollama

# Se parado, iniciar
sudo systemctl start ollama
**Causa 2: Firewall bloqueando**
```bash
# No servidor Ollama
sudo ufw status

# Permitir porta
sudo ufw allow 11434/tcp
**Causa 3: Ollama só escutando localhost**
```bash
# Editar configuração
sudo nano /etc/systemd/system/ollama.service

# Adicionar variável de ambiente
Environment="OLLAMA_HOST=0.0.0.0"

# Reiniciar
sudo systemctl daemon-reload
sudo systemctl restart ollama
**Causa 4: Modelo não existe**
```bash
# Verificar modelos disponíveis
curl http://192.168.15.2:11434/api/tags | jq '.models[].name'

# Se eddie-coder não existir, criar
ollama create eddie-coder -f eddie-homelab.Modelfile
---

### 4. Docker Não Funciona

#### Sintomas
- Erro ao criar containers
- Permissão negada

#### Causas e Soluções

**Causa 1: Usuário não está no grupo docker**
```bash
# Verificar
groups $USER | grep docker

# Adicionar ao grupo
sudo usermod -aG docker $USER

# Aplicar mudanças (relogar ou)
newgrp docker
**Causa 2: Docker daemon não está rodando**
```bash
# Verificar
systemctl status docker

# Iniciar
sudo systemctl start docker
**Causa 3: Espaço em disco insuficiente**
```bash
# Verificar espaço
df -h

# Limpar imagens não utilizadas
docker system prune -a

# Limpar volumes não utilizados
docker volume prune
---

### 5. RAG Não Encontra Resultados

#### Sintomas
- Buscas retornam vazio
- Contexto não é usado

#### Causas e Soluções

**Causa 1: Base de dados vazia**
```bash
# Verificar coleções
python3 << 'EOF'
import chromadb
client = chromadb.PersistentClient(path="/home/homelab/myClaude/chroma_db")
for col in client.list_collections():
    print(f"{col.name}: {col.count()} documentos")
EOF
**Causa 2: Diretório ChromaDB não existe**
```bash
# Criar diretório
mkdir -p /home/homelab/myClaude/chroma_db

# Dar permissões
chmod 755 /home/homelab/myClaude/chroma_db
**Causa 3: Modelo de embedding não instalado**
```bash
# Instalar sentence-transformers
pip install sentence-transformers

# Testar
python3 -c "from sentence_transformers import SentenceTransformer; print('OK')"
---

### 6. GitHub Push Falha

#### Sintomas
- Erro de autenticação
- Push rejeitado

#### Causas e Soluções

**Causa 1: Token inválido ou expirado**
```bash
# Testar token
curl -H "Authorization: token <TOKEN>" https://api.github.com/user

# Se retornar erro, gerar novo token
# GitHub → Settings → Developer settings → Personal access tokens
**Causa 2: Token sem permissões**
```bash
# O token precisa das permissões:
# - repo (full control)
# - workflow (opcional, para Actions)
**Causa 3: Repositório já existe**
```bash
# Se o repo já existe, usar push normal
git push origin main

# Ou deletar e recriar
curl -X DELETE -H "Authorization: token <TOKEN>" \
  https://api.github.com/repos/<USER>/<REPO>
---

### 7. Auto-Desenvolvimento Não Funciona

#### Sintomas
- Bot não desenvolve automaticamente
- Mensagem "não sei" não dispara desenvolvimento

#### Causas e Soluções

**Causa 1: API dos agentes offline**
```bash
# Verificar
curl http://localhost:8503/health

# Iniciar se necessário
cd ~/myClaude/specialized_agents
~/.local/bin/uvicorn api:app --host 0.0.0.0 --port 8503 &
**Causa 2: Padrões de detecção não correspondendo**
```bash
# Verificar no código os padrões
grep -A 20 "INABILITY_PATTERNS" /home/homelab/myClaude/telegram_bot.py
**Causa 3: Erro na detecção de linguagem**
```bash
# Verificar logs
journalctl -u eddie-telegram-bot -n 100 | grep -i "detect\|linguagem"
---

## Logs e Debugging

### Onde Encontrar Logs

```bash
# Bot Telegram
journalctl -u eddie-telegram-bot -f

# API Agentes
journalctl -u specialized-agents -f

# Ollama (no servidor)
journalctl -u ollama -f

# Docker
docker logs <container_id>
### Aumentar Nível de Log

# Adicionar no início do script
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
### Capturar Exceções

import traceback

try:
    # código
except Exception as e:
    print(f"Erro: {e}")
    traceback.print_exc()
---

## Scripts de Recuperação

### Reiniciar Todo o Sistema

```bash
#!/bin/bash
echo "Parando serviços..."
sudo systemctl stop eddie-telegram-bot
sudo systemctl stop specialized-agents

echo "Limpando..."
pkill -f telegram_bot.py
pkill -f "uvicorn api:app"

echo "Iniciando API..."
sudo systemctl start specialized-agents
sleep 5

echo "Iniciando Bot..."
sudo systemctl start eddie-telegram-bot
sleep 3

echo "Verificando..."
curl -s http://localhost:8503/health
pgrep -af telegram_bot

echo "Done!"
### Resetar RAG

```bash
#!/bin/bash
echo "⚠️ Isso vai apagar todo o RAG!"
read -p "Continuar? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf /home/homelab/myClaude/chroma_db/*
    echo "RAG resetado. Reindexe o conteúdo."
fi
### Limpar Docker

```bash
#!/bin/bash
echo "Parando todos containers..."
docker stop $(docker ps -aq) 2>/dev/null

echo "Removendo containers..."
docker rm $(docker ps -aq) 2>/dev/null

echo "Removendo imagens não utilizadas..."
docker image prune -a -f

echo "Removendo volumes não utilizados..."
docker volume prune -f

echo "Status:"
docker system df
---

## Contato e Suporte

### Informações do Sistema

```bash
# Coletar informações para suporte
echo "=== System Info ===" > /tmp/eddie-debug.txt
uname -a >> /tmp/eddie-debug.txt
python3 --version >> /tmp/eddie-debug.txt
docker --version >> /tmp/eddie-debug.txt

echo "=== Services ===" >> /tmp/eddie-debug.txt
systemctl status eddie-telegram-bot >> /tmp/eddie-debug.txt 2>&1
systemctl status specialized-agents >> /tmp/eddie-debug.txt 2>&1

echo "=== Last Logs ===" >> /tmp/eddie-debug.txt
journalctl -u eddie-telegram-bot -n 50 >> /tmp/eddie-debug.txt 2>&1

cat /tmp/eddie-debug.txt
### Verificação de Saúde Completa

```bash
#!/bin/bash
# health_check.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
    if $2 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        return 1
    fi
}

echo "Eddie Auto-Dev Health Check"
echo "=========================="

check "Python" "python3 --version"
check "Docker" "docker ps"
check "Bot Process" "pgrep -f telegram_bot"
check "API Health" "curl -s http://localhost:8503/health"
check "Ollama" "curl -s http://192.168.15.2:11434/api/tags"
check "ChromaDB Dir" "test -d /home/homelab/myClaude/chroma_db"

echo ""
echo "Ports:"
lsof -i :8503 | grep LISTEN || echo "8503: not in use"
