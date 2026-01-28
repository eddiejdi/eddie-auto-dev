#!/usr/bin/env bash
set -euo pipefail

# start_localtunnel.sh
# Instruções: execute `./start_localtunnel.sh --port 3000 --subdomain mysubdomain`
# Requer: node/npm (ou usa npx automaticamente)

PORT=3000
SUBDOMAIN=""
SECRETS_FILE="tools/simple_vault/secrets/public_tunnel_url.txt"

usage(){
  echo "Usage: $0 --port <port> [--subdomain <name>]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --subdomain) SUBDOMAIN="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

echo "Iniciando LocalTunnel para porta $PORT..."

# Use npx so não é necessário instalação global
if [ -n "$SUBDOMAIN" ]; then
  LT_CMD=(npx localtunnel --port "$PORT" --subdomain "$SUBDOMAIN")
else
  LT_CMD=(npx localtunnel --port "$PORT")
fi

echo "Executando: ${LT_CMD[*]}"

# Executa e captura a saída para extrair a URL pública
TMP=$(mktemp)
"
${LT_CMD[@]}" | tee "$TMP" &
LT_PID=$!

echo "Aguardando saída do localtunnel para capturar URL (primeiros 10s)..."
sleep 10

URL_LINE=$(grep -Eo "https?://[a-zA-Z0-9.:-_/]+" "$TMP" | head -n1 || true)
if [ -z "$URL_LINE" ]; then
  echo "Não foi possível capturar a URL do LocalTunnel automaticamente. Veja a saída do processo:" >&2
  tail -n 50 "$TMP"
  echo "Se preferir, abra um outro terminal e execute: ${LT_CMD[*]}" >&2
  exit 1
fi

echo "URL pública encontrada: $URL_LINE"

mkdir -p "$(dirname "$SECRETS_FILE")"
echo "PUBLIC_TUNNEL_URL=$URL_LINE" > "$SECRETS_FILE"
chmod 600 "$SECRETS_FILE" || true
echo "URL salva em $SECRETS_FILE"

echo "O processo do LocalTunnel está rodando (PID=$LT_PID). Pressione CTRL-C para encerrar." 
wait $LT_PID
