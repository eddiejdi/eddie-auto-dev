#!/usr/bin/env bash
set -euo pipefail

# ===========================================================
# Setup completo do Cloudflare Tunnel RPA4All
# Inclui TODOS os serviços + Wiki.js
# Requer: sudo, cloudflared instalado
# ===========================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

TUNNEL_NAME="rpa4all-homelab"
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config.yml"

echo -e "${GREEN}=== Cloudflare Tunnel Setup — RPA4All ===${NC}"

# 1. Verificar cloudflared
if ! command -v cloudflared &>/dev/null; then
    echo -e "${RED}cloudflared não encontrado. Instalando...${NC}"
    curl -sL -o /tmp/cloudflared.deb \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
    sudo dpkg -i /tmp/cloudflared.deb
    rm -f /tmp/cloudflared.deb
fi
echo -e "${GREEN}✅ cloudflared $(cloudflared --version 2>&1 | head -1)${NC}"

# 2. Autenticação
echo ""
if [ ! -f "$CONFIG_DIR/cert.pem" ]; then
    echo -e "${YELLOW}🔐 Autenticação necessária. Um link será exibido — abra no browser.${NC}"
    cloudflared tunnel login
    echo -e "${GREEN}✅ Autenticado${NC}"
else
    echo -e "${GREEN}✅ Já autenticado (cert.pem existe)${NC}"
fi

# 3. Criar tunnel (se não existir)
echo ""
EXISTING=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || true)
if [ -z "$EXISTING" ]; then
    echo -e "${YELLOW}🚇 Criando tunnel '$TUNNEL_NAME'...${NC}"
    cloudflared tunnel create "$TUNNEL_NAME"
else
    echo -e "${GREEN}✅ Tunnel '$TUNNEL_NAME' já existe${NC}"
fi

TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
echo -e "   Tunnel ID: ${GREEN}$TUNNEL_ID${NC}"

# 4. Gerar config.yml
echo ""
echo -e "${YELLOW}⚙️  Gerando config.yml...${NC}"
mkdir -p "$CONFIG_DIR"

CREDS_FILE="$CONFIG_DIR/${TUNNEL_ID}.json"
if [ ! -f "$CREDS_FILE" ]; then
    # Tentar raiz também
    CREDS_FILE="/root/.cloudflared/${TUNNEL_ID}.json"
fi

cat > "$CONFIG_FILE" <<EOF
# Cloudflare Tunnel — RPA4All Homelab
# Gerado automaticamente em $(date -I)
tunnel: $TUNNEL_ID
credentials-file: $CREDS_FILE

ingress:
  # Authentik SSO
  - hostname: auth.rpa4all.com
    service: http://127.0.0.1:9000
    originRequest:
      noTLSVerify: false

  # Wiki.js (Documentação interna)
  - hostname: wiki.rpa4all.com
    service: http://127.0.0.1:3009
    originRequest:
      noTLSVerify: false

  # IDE Web
  - hostname: ide.rpa4all.com
    service: http://127.0.0.1:8081
    originRequest:
      noTLSVerify: false

  # Open WebUI (Chat IA)
  - hostname: openwebui.rpa4all.com
    service: http://127.0.0.1:3000
    originRequest:
      noTLSVerify: false

  # Grafana (Monitoramento)
  - hostname: grafana.rpa4all.com
    service: http://127.0.0.1:3001
    originRequest:
      noTLSVerify: false

  # API — Code Runner
  - hostname: api.rpa4all.com
    path: /code-runner/*
    service: http://127.0.0.1:2000
    originRequest:
      connectTimeout: 60s

  # API — Specialized Agents
  - hostname: api.rpa4all.com
    path: /agents-api/*
    service: http://127.0.0.1:8503
    originRequest:
      connectTimeout: 60s

  # Catch-all
  - service: http_status:404

loglevel: info
logfile: /var/log/cloudflared.log
no-autoupdate: false
grace-period: 30s
EOF

echo -e "${GREEN}✅ Config gerado: $CONFIG_FILE${NC}"

# 5. Registrar DNS
echo ""
echo -e "${YELLOW}🌐 Registrando DNS...${NC}"
for HOSTNAME in wiki.rpa4all.com auth.rpa4all.com ide.rpa4all.com openwebui.rpa4all.com grafana.rpa4all.com api.rpa4all.com; do
    cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME" 2>/dev/null && \
        echo -e "   ${GREEN}✅ $HOSTNAME${NC}" || \
        echo -e "   ${YELLOW}⚠️  $HOSTNAME (já existe ou falhou)${NC}"
done

# 6. Instalar serviço systemd
echo ""
echo -e "${YELLOW}🔧 Instalando serviço systemd...${NC}"
sudo cloudflared service install 2>/dev/null && \
    echo -e "${GREEN}✅ Serviço instalado${NC}" || \
    echo -e "${YELLOW}⚠️  Serviço já instalado${NC}"

sudo systemctl enable cloudflared 2>/dev/null
sudo systemctl restart cloudflared 2>/dev/null

# 7. Verificar
echo ""
echo -e "${GREEN}=== Status ===${NC}"
sleep 3
sudo systemctl status cloudflared --no-pager -l 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Setup concluído!${NC}"
echo ""
echo "URLs disponíveis:"
echo "  🔐 https://auth.rpa4all.com (Authentik SSO)"
echo "  📚 https://wiki.rpa4all.com (Wiki.js)"
echo "  💻 https://ide.rpa4all.com (IDE Web)"
echo "  💬 https://openwebui.rpa4all.com (Chat IA)"
echo "  📊 https://grafana.rpa4all.com (Grafana)"
echo "  🤖 https://api.rpa4all.com (Agents API)"
