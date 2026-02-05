#!/bin/bash
# Script para abrir Grafana com SSH Tunnel
# Uso: ./open_grafana.sh

echo "🧠 Abrindo Dashboard Neural do Grafana..."
echo

# Verificar se já existe tunnel aberto
if netstat -tuln 2>/dev/null | grep -q "3002" || lsof -Pi :3002 -sTCP:LISTEN 2>/dev/null; then
    echo "✅ Tunnel SSH já existe na porta 3002"
else
    echo "🔧 Criando SSH Tunnel..."
    ssh -N -L 3002:localhost:3002 homelab@192.168.15.2 &
    TUNNEL_PID=$!
    echo "✅ Tunnel PID: $TUNNEL_PID"
    sleep 2
fi

# Verificar se consegue acessar
echo
echo "🔍 Verificando conexão..."
if curl -s -I http://localhost:3002/grafana | grep -q "302"; then
    echo "✅ Grafana está acessível!"
    echo
    echo "📍 URLs disponíveis:"
    echo "  Dashboard Neural: http://localhost:3002/grafana/d/neural-network-v1/"
    echo "  Home:            http://localhost:3002/grafana/"
    echo "  API Health:      http://localhost:3002/api/health"
    echo
    echo "🔐 Credenciais:"
    echo "  Usuário: admin"
    echo "  Senha:   newpassword123"
    echo
    
    # Tentar abrir no navegador padrão
    if command -v xdg-open &> /dev/null; then
        echo "🌐 Abrindo no navegador..."
        xdg-open "http://localhost:3002/grafana/d/neural-network-v1/" &
    elif command -v open &> /dev/null; then
        echo "🌐 Abrindo no navegador..."
        open "http://localhost:3002/grafana/d/neural-network-v1/" &
    else
        echo "⚠️  Copie a URL no navegador manualmente"
    fi
else
    echo "❌ Erro ao conectar ao Grafana"
    echo "Verifique:"
    echo "  1. SSH está conectado?"
    echo "  2. Container Grafana está rodando?"
    echo "  3. Firewall bloqueando porta 3002?"
    exit 1
fi
