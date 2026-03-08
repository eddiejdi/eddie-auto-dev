#!/bin/bash
# Deploy para Produção (Homelab)

PROD_HOST="192.168.15.2"
PROD_USER="homelab"
PROD_PATH="/home/homelab/myClaude"

echo "================================================"
echo "DEPLOY - Produção (Homelab)"
echo "================================================"
echo "Host: $PROD_HOST"
echo "Path: $PROD_PATH"
echo ""

# 1. SSH conectar e atualizar repo
echo "[1/4] Atualizando repositório em PROD..."
ssh -o StrictHostKeyChecking=no $PROD_USER@$PROD_HOST << 'SSH_EOF'
cd /home/homelab/myClaude
git fetch origin main
git reset --hard origin/main
echo "✓ Repositório atualizado"
SSH_EOF

# 2. Parar serviço atual
echo ""
echo "[2/4] Parando serviço atual..."
ssh -o StrictHostKeyChecking=no $PROD_USER@$PROD_HOST << 'SSH_EOF'
sudo systemctl stop specialized-agents 2>/dev/null || echo "Serviço não estava rodando"
sleep 2
echo "✓ Serviço parado"
SSH_EOF

# 3. Iniciar novo serviço
echo ""
echo "[3/4] Iniciando novo serviço..."
ssh -o StrictHostKeyChecking=no $PROD_USER@$PROD_HOST << 'SSH_EOF'
cd /home/homelab/myClaude
nohup python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503 > /var/log/specialized-agents.log 2>&1 &
sleep 4
echo "✓ Serviço iniciado"
SSH_EOF

# 4. Validar saúde
echo ""
echo "[4/4] Validando saúde..."
HEALTH=$(ssh -o StrictHostKeyChecking=no $PROD_USER@$PROD_HOST "curl -s http://localhost:8503/health 2>/dev/null || echo 'TIMEOUT'")

if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ Saúde: OK"
    echo ""
    echo "================================================"
    echo "✅ DEPLOY SUCESSO"
    echo "================================================"
else
    echo "✗ Saúde: FALHOU"
    echo "Resposta: $HEALTH"
    echo ""
    echo "================================================"
    echo "❌ DEPLOY FALHOU"
    echo "================================================"
    exit 1
fi
