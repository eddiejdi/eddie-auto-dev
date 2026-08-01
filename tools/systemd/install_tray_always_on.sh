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

# 2. Instalar drop-in da API (sem segredo: ele aponta para o EnvironmentFile)
mkdir -p "$SYSTEMD_DIR/specialized-agents-api.service.d"
cp "$REPO_DIR/tools/systemd/specialized-agents-api-ha.conf" \
   "$SYSTEMD_DIR/specialized-agents-api.service.d/ha.conf"
echo "   ✅ drop-in ha.conf instalado"

# 2b. Materializar o token do HA fora do git, a partir do Secrets Agent.
# O drop-in é versionado num repo público — o valor não pode morar nele.
mkdir -p /etc/eddie
HA_ENV="/etc/eddie/home-assistant.env"
if HA_TOKEN=$(cd "$REPO_DIR" && python3 -c "
from tools.secrets_loader import get_field
print(get_field('eddie/home_assistant_token', 'password'))
" 2>/dev/null) && [ -n "$HA_TOKEN" ]; then
    # umask antes do redirect: sem isso o arquivo nasce 0644 por um instante.
    ( umask 077; printf 'HOME_ASSISTANT_TOKEN=%s\n' "$HA_TOKEN" > "$HA_ENV" )
    chmod 0600 "$HA_ENV"
    echo "   ✅ $HA_ENV gerado a partir do Secrets Agent (0600)"
else
    echo "   ⚠️  Secrets Agent não respondeu — $HA_ENV não foi atualizado."
    echo "      A API sobe, mas chamadas ao Home Assistant vão falhar até que"
    echo "      o secret 'eddie/home_assistant_token' esteja acessível."
fi

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
