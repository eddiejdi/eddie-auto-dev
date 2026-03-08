# 🔧 CORREÇÃO PERMANENTE: DATABASE_URL no BTC Agent

**Problema Identificado**: Variável `DATABASE_URL` estava hardcoded no ambiente do shell com IP antigo (192.168.15.2), sobrescrevendo o valor do .env

**Solução Implementada**: Passar DATABASE_URL na linha de comando CLI

---

## 📋 Opções de Configuração Permanente

### Opção 1: Via Systemd Service (RECOMENDADO)

Criar `/etc/systemd/system/btc-trading-agent.service`:

```ini
[Unit]
Description=BTC Trading Agent - LIVE Mode
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/myClaude/btc_trading_agent
Environment="DATABASE_URL=postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres"
ExecStart=/usr/bin/python3 /home/homelab/myClaude/btc_trading_agent/trading_agent.py --daemon --live
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=btc-agent

[Install]
WantedBy=multi-user.target
```

**Ativar**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable btc-trading-agent
sudo systemctl start btc-trading-agent
sudo journalctl -u btc-trading-agent -f
```

---

### Opção 2: Via Shell Script com Alias

Criar `/home/homelab/btc_restart.sh`:

```bash
#!/bin/bash
set -e

export DATABASE_URL="postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres"
cd /home/homelab/myClaude/btc_trading_agent

# Kill existing process
pkill -f "trading_agent.py.*--live" || true

# Start fresh
/usr/bin/python3 trading_agent.py --daemon --live

echo "✅ BTC Trading Agent started with DATABASE_URL=172.17.0.2"
```

**Setup**:
```bash
chmod +x /home/homelab/btc_restart.sh
alias btc-restart='/home/homelab/btc_restart.sh'
# Adicionar ao ~/.bashrc
```

---

### Opção 3: Via Docker Compose (FUTURO)

Encapsular agente em container com env vardefinidas:

```yaml
services:
  btc-trading-agent:
    build: ./btc_trading_agent
    environment:
      - DATABASE_URL=postgresql://postgres:shared_memory_2026@shared-postgres:5432/postgres
      - KUCOIN_API_KEY=${KUCOIN_API_KEY}
      - KUCOIN_API_SECRET=${KUCOIN_API_SECRET}
      - KUCOIN_API_PASSPHRASE=${KUCOIN_API_PASSPHRASE}
    depends_on:
      - shared-postgres
    restart: always
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
```

---

## 🔍 Diagnóstico: Por que DATABASE_URL era "errado"?

### Análise de Causa Raiz

1. **Variável no Shell**:
   - `echo $DATABASE_URL` mostrava `postgresql://...@192.168.15.2:5432/postgres`
   - Provável origem: /home/homelab/.bashrc ou /home/homelab/.bash_profile

2. **Prioridade de Leitura** (do mais alto para mais baixo):
   - [1] Variável de ambiente do shell (`export DATABASE_URL=...`)
   - [2] Arquivo .env (`.env` da pasta atual)
   - [3] Padrão hardcoded no código Python

3. **O que Acontecia**:
   ```python
   # training_db.py line 20
   DATABASE_URL = os.getenv(
       'DATABASE_URL',
       'postgresql://postgres:shared_memory_2026@localhost:5432/postgres'
   )
   ```
   - O shell tinha `DATABASE_URL=...@192.168.15.2:5432/postgres` definido globalmente
   - Mesmo com .env tendo 172.17.0.2, o `os.getenv()` pegava o valor do shell

---

## ✅ Verificação da Correção

```bash
# 1. Confirmar que DATABASE_URL está correto
echo $DATABASE_URL
# Deve mostrar: postgresql://postgres:shared_memory_2026@127.0.0.1:5433/postgres
# OU: postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres

# 2. Verificar connection string do código
ssh homelab@192.168.15.2 'grep -n "^DATABASE_URL" /home/homelab/myClaude/btc_trading_agent/.env'

# 3. Testar conexão direto
psql -h 172.17.0.2 -p 5432 -U postgres -d postgres -c "SELECT version();"
```

---

## 🔴 Emergency: Resetar DATABASE_URL

Se o problema voltar:

```bash
# 1. Limpar variável do shell
unset DATABASE_URL

# 2. Confirmar
echo $DATABASE_URL  # Deve estar vazio

# 3. Reiniciar agente
cd /home/homelab/myClaude/btc_trading_agent
DATABASE_URL=postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres \
/usr/bin/python3 trading_agent.py --daemon --live
```

---

## 📊 Teste: Validar Connection Pool

```bash
# SSH para homelab
ssh homelab@192.168.15.2

# Entrar no diretório
cd /home/homelab/myClaude/btc_trading_agent

# Testar import e connection
python3 << 'EOF'
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres'

from training_db import TrainingDatabase

try:
    db = TrainingDatabase()
    print("✅ Connection pool initialized successfully")
    print(f"   URL: {os.getenv('DATABASE_URL')}")
    db.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
EOF
```

---

## 🎯 Recomendação Final

**Use Opção 1 (Systemd Service)** porque:
- ✅ Persistente entre reboots
- ✅ Fácil de monitorar (`systemctl status`)
- ✅ Logs centralizados (`journalctl`)
- ✅ Integrado com infraestrutura existente
- ✅ Restart automático se process morrer

**Setup Estimado**: 5 minutos
**Impacto**: Zero on production (substitui manual restart)

---

**Data**: 2026-02-26
**Agente**: BTC Trading
**Próxima Ação**: Implementar Opção 1 (Systemd Service)
