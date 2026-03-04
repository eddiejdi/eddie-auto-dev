#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="/var/lib/eddie/secrets_agent"
PW_FILE="${DATA_DIR}/.bw_master_password"
UNIT_NAME="secrets_agent.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
DROP_IN_DIR="/etc/systemd/system/${UNIT_NAME}.d"

echo "═══ Instalando Secrets Agent v2.0 (auto-unlock BW) ═══"

# ── 1. Diretório de dados ──
sudo mkdir -p "${DATA_DIR}"
sudo chown -R "$(whoami):$(whoami)" "${DATA_DIR}"
echo "✓ Diretório de dados: ${DATA_DIR}"

# ── 2. Arquivo de master password (se ainda não existe) ──
if [[ ! -f "${PW_FILE}" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Para auto-unlock do Bitwarden sem solicitar senha:         ║"
    echo "║  Crie o arquivo com a master password:                      ║"
    echo "║                                                             ║"
    echo "║  echo 'SUA_MASTER_PASSWORD' > ${PW_FILE}"
    echo "║  chmod 600 ${PW_FILE}"
    echo "║                                                             ║"
    echo "║  O Secrets Agent vai usar este arquivo para auto-unlock.    ║"
    echo "║  Sem ele, apenas secrets locais (SQLite) estarão acessíveis.║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
else
    chmod 600 "${PW_FILE}"
    echo "✓ Arquivo de master password encontrado: ${PW_FILE}"
fi

# ── 3. Verificar se BW CLI está logado ──
BW_STATUS=$(bw status 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unavailable")
echo "✓ Status BW CLI: ${BW_STATUS}"

if [[ "${BW_STATUS}" == "unauthenticated" ]]; then
    echo ""
    echo "⚠  BW não está logado. Para login interativo (uma única vez):"
    echo "   bw login"
    echo ""
    echo "   Ou para login via API key (non-interactive):"
    echo "   export BW_CLIENTID='user.xxx'"
    echo "   export BW_CLIENTSECRET='xxx'"
    echo "   bw login --apikey"
    echo ""
    echo "   Após login, o Secrets Agent faz auto-unlock automaticamente."
fi

# ── 4. Copiar unit file ──
sudo cp tools/secrets_agent/secrets_agent.service "${UNIT_PATH}"
echo "✓ Unit file copiado para ${UNIT_PATH}"

# ── 5. Criar/atualizar drop-in com API key ──
sudo mkdir -p "${DROP_IN_DIR}"
if [[ ! -f "${DROP_IN_DIR}/override.conf" ]]; then
    API_KEY="${SECRETS_AGENT_API_KEY:-$(openssl rand -hex 32)}"
    cat <<EOF | sudo tee "${DROP_IN_DIR}/override.conf" > /dev/null
[Service]
Environment=SECRETS_AGENT_API_KEY=${API_KEY}
EOF
    echo "✓ API key gerada e salva em ${DROP_IN_DIR}/override.conf"
    echo "  Guarde esta chave: ${API_KEY}"
else
    echo "✓ Drop-in override.conf existente mantido"
fi

# ── 6. Ativar e iniciar serviço ──
sudo systemctl daemon-reload
sudo systemctl enable --now "${UNIT_NAME}"
echo "✓ Serviço ${UNIT_NAME} ativado e iniciado"

# ── 7. Verificar saúde ──
sleep 3
if curl -sf --connect-timeout 5 http://127.0.0.1:8088/health > /dev/null 2>&1; then
    echo "✓ Health check OK — Secrets Agent rodando em :8088"
    # Mostrar status BW
    BW_INFO=$(curl -sf http://127.0.0.1:8088/bw/status 2>/dev/null || echo '{"bw_status":"unknown"}')
    echo "  BW Status: ${BW_INFO}"
else
    echo "⚠ Health check falhou — verifique logs: journalctl -u ${UNIT_NAME} -n 20"
fi

echo ""
echo "═══ Instalação concluída ═══"
echo "  API:       http://127.0.0.1:8088"
echo "  Métricas:  http://127.0.0.1:8009"
echo "  BW Status: curl http://127.0.0.1:8088/bw/status"
echo "  Logs:      journalctl -u ${UNIT_NAME} -f"
