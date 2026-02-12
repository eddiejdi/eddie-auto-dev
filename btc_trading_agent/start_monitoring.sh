#!/bin/bash
###############################################################################
# Quick Start - Grafana Dashboard for AutoCoinBot
# Script rápido para iniciar monitoramento
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Iniciando monitoramento do AutoCoinBot..."
echo ""

# 1. Iniciar Prometheus Exporter
echo "📊 Iniciando Prometheus Exporter..."
cd "$SCRIPT_DIR"
../.venv/bin/python3 prometheus_exporter.py > logs/exporter.log 2>&1 &
EXPORTER_PID=$!
echo "   PID: $EXPORTER_PID"
sleep 2

# 2. Verificar se está rodando
if curl -s http://localhost:9092/health > /dev/null 2>&1; then
    echo "   ✅ Exporter iniciado com sucesso!"
else
    echo "   ❌ Erro ao iniciar exporter"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✅ MONITORAMENTO ATIVO                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Endpoints:"
echo "   • Health:  http://localhost:9092/health"
echo "   • Metrics: http://localhost:9092/metrics"
echo ""
echo "📈 Ver métricas em tempo real:"
echo "   watch -n 5 'curl -s http://localhost:9092/metrics | grep btc_trading'"
echo ""
echo "🛑 Para parar:"
echo "   kill $EXPORTER_PID"
echo "   # ou"
echo "   pkill -f prometheus_exporter.py"
echo ""
echo "📚 Para instalar Grafana completo:"
echo "   ./setup_grafana.sh"
echo ""
echo "💡 Deixe este terminal aberto (Ctrl+C para parar)"
echo ""

# Manter vivo e mostrar logs
tail -f logs/exporter.log 2>/dev/null &
TAIL_PID=$!

# Trap para cleanup
trap "kill $EXPORTER_PID $TAIL_PID 2>/dev/null; echo ''; echo '👋 Monitoramento encerrado'; exit" INT TERM

# Aguardar
wait $EXPORTER_PID
