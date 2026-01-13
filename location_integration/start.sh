#!/bin/bash
# Script para iniciar o servidor de localização

cd /home/eddie/myClaude/location_integration

# Verificar se já está rodando
if pgrep -f "location_server.py" > /dev/null; then
    echo "⚠️  Servidor já está rodando!"
    pgrep -f "location_server.py"
    exit 0
fi

# Iniciar servidor
echo "🌍 Iniciando Eddie Location Server..."
./venv/bin/python location_server.py &

# Aguardar inicialização
sleep 3

# Testar
if curl -s http://localhost:8585/status > /dev/null; then
    echo "✅ Servidor rodando em http://localhost:8585"
    curl -s http://localhost:8585/status | python3 -m json.tool
else
    echo "❌ Erro ao iniciar servidor"
fi
