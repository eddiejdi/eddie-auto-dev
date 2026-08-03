#!/bin/bash
set -euo pipefail

# Teste rápido do coordenador com consciência de RAM
# Executa localmente na workstation antes de implantar na produção

echo "🔍 Testando coordenador de GPUs..."

# Verifica se os arquivos existem
COORDINATOR="/workspace/eddie-auto-dev/tools/ollama_gpu_coordinator.py"
EXPORTER="/workspace/eddie-auto-dev/tools/nas_ram_exporter.py"

if [[ ! -f "$COORDINATOR" ]]; then
    echo "❌ Coordenador não encontrado em $COORDINATOR"
    exit 1
fi

if [[ ! -f "$EXPORTER" ]]; then
    echo "❌ Exporter RAM não encontrado em $EXPORTER"
    exit 1
fi

echo "✅ Arquivos encontrados"

# Testa sintaxe Python
echo "→ Validando sintaxe Python..."
python3 -m py_compile "$COORDINATOR" && echo "✅ Coordenador OK"
python3 -m py_compile "$EXPORTER" && echo "✅ Exporter OK"

# Verifica variáveis ambientais
echo ""
echo "→ Variáveis configuradas no service file:"
grep "Environment=.*NAS\|Environment=.*RAM" /workspace/eddie-auto-dev/systemd/ollama-gpu-coordinator.service || echo "  (nenhuma encontrada)"

# Testa exporter localmente
echo ""
echo "→ Iniciando exporter RAM em background..."
timeout 5 python3 "$EXPORTER" &
EXPORTER_PID=$!
sleep 2

if kill -0 $EXPORTER_PID 2>/dev/null; then
    echo "✅ Exporter iniciado (PID: $EXPORTER_PID)"
    curl -s http://127.0.0.1:11447/ram | jq . && echo "✅ Endpoint /ram respondendo"
    kill $EXPORTER_PID 2>/dev/null || true
else
    echo "⚠️  Exporter não iniciou (normal se porta já estiver em uso)"
fi

echo ""
echo "📋 Para iniciar o coordenador:"
echo "   sudo cp /workspace/eddie-auto-dev/systemd/ollama-gpu-coordinator.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now ollama-gpu-coordinator"
echo ""
echo "📋 Para implantar na NAS (após configurar SSH):"
echo "   /workspace/eddie-auto-dev/scripts/deploy-nas-ram-exporter.sh"
