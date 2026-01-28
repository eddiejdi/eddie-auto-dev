#!/usr/bin/env bash
set -euo pipefail

# start_remote_tunnel.sh
# Destinado a ser instalado em hosts remotos. Inicia localtunnel, captura a URL
# pública e grava em /var/lib/eddie/public_tunnel_<env>.txt

PORT=3000
SUBDOMAIN=""
ENV_NAME="default"
OUT_DIR="/var/lib/eddie"
OUT_FILE=""

usage(){
  echo "Usage: $0 --port <port> --env <env-name> [--subdomain <name>]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --subdomain) SUBDOMAIN="$2"; shift 2 ;;
    --env) ENV_NAME="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

OUT_FILE="$OUT_DIR/public_tunnel_${ENV_NAME}.txt"

mkdir -p "$OUT_DIR"

echo "Iniciando LocalTunnel na porta $PORT (env=$ENV_NAME) ..."

# Use npx para não exigir instalação global
if [ -n "$SUBDOMAIN" ]; then
  CMD=(npx localtunnel --port "$PORT" --subdomain "$SUBDOMAIN")
else
  CMD=(npx localtunnel --port "$PORT")
fi

TMP=$(mktemp)
"${CMD[@]}" | tee "$TMP" &
LT_PID=$!

echo "Aguardando 8s para capturar a URL pública..."
sleep 8

URL_LINE=$(grep -Eo "https?://[a-zA-Z0-9.:-_/]+" "$TMP" | head -n1 || true)
if [ -z "$URL_LINE" ]; then
  echo "Não foi possível capturar a URL do LocalTunnel automaticamente." >&2
  tail -n 50 "$TMP"
  kill $LT_PID 2>/dev/null || true
  exit 1
fi

echo "URL pública encontrada: $URL_LINE"

echo "PUBLIC_TUNNEL_URL=$URL_LINE" > "$OUT_FILE"
chmod 640 "$OUT_FILE" || true
chown root:root "$OUT_FILE" || true

echo "URL salva em $OUT_FILE"

echo "LocalTunnel PID=$LT_PID em execução; deixar em foreground para systemd." 
wait $LT_PID
