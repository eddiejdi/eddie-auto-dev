#!/usr/bin/env bash
set -euo pipefail

# ===========================================================
# Adiciona rota wiki.rpa4all.com ao Cloudflare Tunnel existente
# Requer: sudo, cloudflared instalado, tunnel configurado
# ===========================================================

TUNNEL_ID="8169b9cd-a798-4610-b3a6-ed7218f6685d"
CONFIG_FILE="/etc/cloudflared/config.yml"
HOSTNAME="wiki.rpa4all.com"
SERVICE="http://localhost:3009"

echo "=== Adicionando Wiki.js ao Cloudflare Tunnel ==="

# 1. Verificar se cloudflared está instalado
if ! command -v cloudflared &>/dev/null; then
    echo "ERRO: cloudflared não encontrado. Instale primeiro."
    exit 1
fi

# 2. Backup do config atual
if [ -f "$CONFIG_FILE" ]; then
    sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backup criado: ${CONFIG_FILE}.bak.*"
else
    echo "AVISO: $CONFIG_FILE não existe. Criando novo..."
    sudo mkdir -p /etc/cloudflared
fi

# 3. Verificar se a rota já existe
if grep -q "$HOSTNAME" "$CONFIG_FILE" 2>/dev/null; then
    echo "Rota para $HOSTNAME já existe no config. Nenhuma ação necessária."
    exit 0
fi

# 4. Adicionar a rota antes do catch-all
# Insere antes da linha "- service: http_status:404"
if grep -q "http_status:404" "$CONFIG_FILE" 2>/dev/null; then
    sudo sed -i "/http_status:404/i\\  - hostname: ${HOSTNAME}\n    service: ${SERVICE}" "$CONFIG_FILE"
    echo "Rota adicionada: $HOSTNAME -> $SERVICE"
else
    echo "AVISO: catch-all não encontrado. Adicionando bloco manualmente..."
    cat <<EOF | sudo tee -a "$CONFIG_FILE" >/dev/null

  - hostname: ${HOSTNAME}
    service: ${SERVICE}
EOF
    echo "Rota adicionada ao final do config"
fi

# 5. Validar configuração
echo ""
echo "=== Config atual ==="
sudo cat "$CONFIG_FILE"

# 6. Registrar DNS CNAME
echo ""
echo "=== Registrando DNS ==="
cloudflared tunnel route dns "$TUNNEL_ID" "$HOSTNAME" 2>/dev/null || \
    echo "AVISO: Falha ao registrar DNS. Verifique manualmente no dashboard Cloudflare."

# 7. Restart do serviço
echo ""
echo "=== Reiniciando cloudflared ==="
sudo systemctl restart cloudflared-rpa4all 2>/dev/null || \
    sudo systemctl restart cloudflared-tunnel 2>/dev/null || \
    echo "AVISO: Serviço não reiniciado automaticamente. Reinicie manualmente."

echo ""
echo "✅ Configuração Wiki.js no tunnel concluída!"
echo "   URL: https://$HOSTNAME"
echo "   Serviço local: $SERVICE"
