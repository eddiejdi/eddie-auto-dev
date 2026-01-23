#!/usr/bin/env bash
# Start an ephemeral cloudflared tunnel for the Streamlit interceptor (port 8501)
# Writes the public URL to .interceptor_tunnel_url and prints export instructions.

set -euo pipefail

OUT_FILE=".interceptor_tunnel_url"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/"
  exit 2
fi

echo "Starting cloudflared tunnel for http://localhost:8501 ..."
# Start ephemeral tunnel in background and capture output
cloudflared tunnel --url http://localhost:8501 > /tmp/cloudflared_interceptor.log 2>&1 &
PID=$!

sleep 2
TAILFILE=/tmp/cloudflared_interceptor.log
URL_LINE=$(grep -oE "https?://[a-zA-Z0-9.-]+\.trycloudflare\.com" "$TAILFILE" | head -n1 || true)

if [ -n "$URL_LINE" ]; then
  echo "$URL_LINE" > "$OUT_FILE"
  echo "Tunnel started: $URL_LINE"
  echo "Export for current shell: export INTERCEPTOR_PUBLIC_URL=$URL_LINE"
  echo "To persist, add to ~/.bashrc or your .env: INTERCEPTOR_PUBLIC_URL=$URL_LINE"
  exit 0
fi

echo "Tunnel started (pid $PID) but public URL not detected immediately. Tail the log at $TAILFILE to see generated URL." 
echo "If you prefer a named tunnel, use 'cloudflared tunnel create' and 'cloudflared tunnel route' per Cloudflare docs."
exit 0
