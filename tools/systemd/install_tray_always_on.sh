#!/usr/bin/env bash
# install_tray_always_on.sh — Instala serviços systemd para always-on
# Uso: sudo bash tools/systemd/install_tray_always_on.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "📦 Instalando Shared Tray Agent service..."

# 1. Instalar serviço do tray agent
cp "$REPO_DIR/tools/systemd/shared-tray-agent.service" "$SYSTEMD_DIR/shared-tray-agent.service"
echo "   ✅ shared-tray-agent.service instalado"

# 2. Adicionar HOME_ASSISTANT_TOKEN ao drop-in da API
mkdir -p "$SYSTEMD_DIR/specialized-agents-api.service.d"
cp "$REPO_DIR/tools/systemd/specialized-agents-api-ha.conf" \
   "$SYSTEMD_DIR/specialized-agents-api.service.d/ha.conf"
echo "   ✅ HOME_ASSISTANT_TOKEN adicionado à API (drop-in ha.conf)"

# 3. Reload systemd
systemctl daemon-reload
echo "   ✅ systemd reloaded"

# 4. Matar processos nohup existentes
echo "🔄 Parando processos nohup residuais..."
pkill -f "python -m shared_tray_agent" 2>/dev/null || true
pkill -f "uvicorn specialized_agents.api:app" 2>/dev/null || true
sleep 2

# 5. Reiniciar API (para pegar o novo token)
systemctl restart specialized-agents-api.service
echo "   ✅ specialized-agents-api reiniciado"

# 6. Habilitar e iniciar tray agent
systemctl enable shared-tray-agent.service
systemctl start shared-tray-agent.service
echo "   ✅ shared-tray-agent habilitado e iniciado"

# 7. Verificar status
echo ""
echo "📊 Status dos serviços:"
systemctl --no-pager status specialized-agents-api.service | head -5
echo "---"
systemctl --no-pager status shared-tray-agent.service | head -5

echo ""
echo "✅ Ambos os serviços estão 'always on' (Restart=always/on-failure)"
echo "   Logs: journalctl -u shared-tray-agent -f"
echo "         journalctl -u specialized-agents-api -f"
