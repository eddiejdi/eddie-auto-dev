#!/bin/bash
# Setup do Review Quality Gate System

set -e

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 Setup: Review Quality Gate System"
echo "═══════════════════════════════════════════════════════════════════════════════"

# 1. Verificar dependências
echo "[1/6] Verificando dependências..."
python3 -c "import sqlite3; print('✅ sqlite3 OK')" || exit 1

# 2. Criar diretórios
echo "[2/6] Criando estrutura de diretórios..."
mkdir -p agent_data/review
mkdir -p logs/review

# 3. Inicializar DB de review queue
echo "[3/6] Inicializando banco de dados de fila de review..."
python3 -c "
from specialized_agents.review_queue import get_review_queue
q = get_review_queue()
print('✅ Review queue DB initialized')
stats = q.get_stats()
print(f'   Total items: {stats[\"total\"]}')
"

# 4. Testar ReviewAgent
echo "[4/6] Testando ReviewAgent..."
python3 -c "
from specialized_agents.review_agent import ReviewAgent
agent = ReviewAgent()
print(f'✅ ReviewAgent initialized: {agent.name}')
status = agent.get_status()
print(f'   Status: {status}')
"

# 5. Criar systemd service
echo "[5/6] Criando systemd service..."
cat > /tmp/review-service.service << 'EOF'
[Unit]
Description=Code Review Quality Gate Service
After=network.target
Requires=specialized-agents-api.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/shared-auto-dev
Environment="PYTHONUNBUFFERED=1"
Environment="REVIEW_SERVICE_POLL_INTERVAL=60"
Environment="REVIEW_SERVICE_BATCH=3"
Environment="REVIEW_SERVICE_AUTO_MERGE=true"
Environment="REVIEW_SERVICE_RUN_TESTS=true"
ExecStart=/usr/bin/python3 /home/homelab/shared-auto-dev/specialized_agents/review_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=review-service

[Install]
WantedBy=multi-user.target
EOF

if [ -f /etc/systemd/system/review-service.service ]; then
    echo "   ℹ️  Service já existe, sobrescrevendo..."
fi

sudo cp /tmp/review-service.service /etc/systemd/system/review-service.service
sudo systemctl daemon-reload
echo "   ✅ Service criado: /etc/systemd/system/review-service.service"

# 6. Integração com API
echo "[6/6] Integrando rotas de review na API..."

# Verificar se já tá integrado
if grep -q "review_routes" specialized_agents/api.py; then
    echo "   ℹ️  Review routes já integradas"
else
    echo "   ⚠️  Adicione isso em api.py:"
    echo "      from specialized_agents.review_routes import router as review_router"
    echo "      app.include_router(review_router)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ Setup concluído!"
echo ""
echo "Próximos passos:"
echo "  1. Integrar review_routes em api.py"
echo "  2. Desabilitar push direto dos agents (via push_interceptor)"
echo "  3. Iniciar service:"
echo "     sudo systemctl start review-service"
echo "     sudo systemctl enable review-service"
echo "  4. Verificar:"
echo "     sudo systemctl status review-service"
echo "     curl http://localhost:8503/review/agent/status"
echo ""
echo "Documentação:"
echo "  docs/REVIEW_QUALITY_GATE.md"
echo "═══════════════════════════════════════════════════════════════════════════════"
