#!/bin/bash
# Deploy do Ollama Dual-GPU Selfheal no homelab
# Uso: bash monitoring/deploy_gpu_selfheal.sh
set -euo pipefail

REMOTE="homelab"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploy Ollama Dual-GPU Selfheal ==="

# 1. Copiar script
echo "[1/6] Copiando script selfheal..."
scp "$SCRIPT_DIR/ollama_gpu_selfheal.sh" "${REMOTE}:/tmp/ollama_gpu_selfheal"
ssh "$REMOTE" 'sudo mv /tmp/ollama_gpu_selfheal /usr/local/bin/ollama_gpu_selfheal && sudo chmod +x /usr/local/bin/ollama_gpu_selfheal'

# 2. Copiar unit systemd
echo "[2/6] Instalando unit systemd..."
scp "$SCRIPT_DIR/ollama-gpu-selfheal.service" "${REMOTE}:/tmp/ollama-gpu-selfheal.service"
ssh "$REMOTE" 'sudo mv /tmp/ollama-gpu-selfheal.service /etc/systemd/system/ollama-gpu-selfheal.service'

# 3. Criar state dir
echo "[3/6] Criando diretórios..."
ssh "$REMOTE" 'sudo mkdir -p /var/lib/ollama-selfheal'

# 4. Parar serviços antigos (não remover, apenas desabilitar)
echo "[4/6] Desabilitando exporters antigos (frozen-monitor + metrics-exporter)..."
ssh "$REMOTE" 'sudo systemctl stop ollama-frozen-monitor.service ollama-metrics-exporter.service 2>/dev/null || true'
ssh "$REMOTE" 'sudo systemctl disable ollama-frozen-monitor.service ollama-metrics-exporter.service 2>/dev/null || true'

# 5. Habilitar e iniciar novo serviço
echo "[5/6] Habilitando e iniciando ollama-gpu-selfheal..."
ssh "$REMOTE" 'sudo systemctl daemon-reload && sudo systemctl enable --now ollama-gpu-selfheal.service'

# 6. Teste rápido
echo "[6/6] Aguardando primeiro ciclo (20s)..."
sleep 20
ssh "$REMOTE" 'cat /var/lib/prometheus/node-exporter/ollama_gpu.prom 2>/dev/null | grep -v "^#" || echo "ERRO: métricas não geradas"'

echo ""
echo "=== Verificando status ==="
ssh "$REMOTE" 'sudo systemctl status ollama-gpu-selfheal --no-pager -l | head -15'
echo ""
echo "Deploy concluído. Regras Grafana devem ser atualizadas separadamente."
