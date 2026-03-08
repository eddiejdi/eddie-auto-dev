#!/bin/bash
# Iniciar dashboard

cd /home/shared/myClaude

# Matar dashboard anterior
pkill -f "python3 dashboard.py" 2>/dev/null || true
sleep 2

# Iniciar novo dashboard
echo "Iniciando Dashboard em tempo real..."
python3 dashboard.py > /tmp/dashboard.log 2>&1 &
sleep 3

# Testar
echo "Testando acesso..."
RESPONSE=$(curl -s http://localhost:8504/ | head -10)
if echo "$RESPONSE" | grep -q "Shared Auto-Dev"; then
    echo "✅ Dashboard funcional"
    echo ""
    echo "🌐 Acesso: http://localhost:8504"
    echo "📊 Mostrando:"
    echo "   - Conversas em tempo real (atualiza a cada 2s)"
    echo "   - Precisão de agentes (Python, JS, Go, Rust, etc)"
    echo "   - Estatísticas gerais"
else
    echo "❌ Dashboard com erro"
    cat /tmp/dashboard.log
fi
