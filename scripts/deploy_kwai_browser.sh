#!/usr/bin/env bash
set -euo pipefail

# Deploy do Kwai Browser — EXECUÇÃO EXCLUSIVA NO SERVIDOR HOMELAB
# Este container roda SOMENTE em 192.168.15.2 (homelab).
# Não há acesso direto da workstation local.
# Motivo: contornar bloqueio de DNS/proxy/VPN que redireciona kwai.com → 127.0.0.1

COMPOSE_FILE="/home/homelab/myClaude/docker/docker-compose.kwai-browser.yml"
ENV_FILE="/home/homelab/docker/kwai-browser/.env"
CONFIG_DIR="/home/homelab/docker/kwai-browser/config"

mkdir -p "$(dirname "$ENV_FILE")" "$CONFIG_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  password="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
  cat >"$ENV_FILE" <<EOF
REWARDS_BROWSER_USER=rewards
REWARDS_BROWSER_PASSWORD=${password}
EOF
  chmod 600 "$ENV_FILE"
  echo "Created ${ENV_FILE}"
fi

echo ">>> Verificando conectividade direta com kwai.com no host (deve bypassar proxy)..."
if ! curl -4 --max-time 8 -I https://www.kwai.com 2>/dev/null | head -1 | grep -q "200\|301\|302"; then
  echo "⚠️  AVISO: curl não conseguiu conectar diretamente ao Kwai."
  echo "    Verifique se *.kwai.com está na lista de bypass do proxy/VPN do homelab."
  echo "    Adicione no arquivo de configuração do proxy: no_proxy=kwai.com,.kwai.com"
fi

docker-compose -p kwai-browser --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
docker-compose -p kwai-browser --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

echo
echo "✅ Kwai browser implantado (isolado no servidor homelab)."
echo "URL (no servidor): https://127.0.0.1:3016/  (aceite o certificado auto-assinado)"
echo "User:     $(grep '^REWARDS_BROWSER_USER=' "$ENV_FILE" | cut -d= -f2-)"
echo "Password: $(grep '^REWARDS_BROWSER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
echo
echo "Acesso da LAN/workstation:"
echo "  ssh -L 3016:127.0.0.1:3016 homelab@192.168.15.2"
echo "  Depois abra: https://localhost:3016/"
echo
echo "⚠️  Lembrete: adicione kwai.com,.kwai.com,m-wallet.kwai.com no bypass do proxy/VPN do homelab."