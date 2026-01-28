#!/usr/bin/env bash
set -euo pipefail

# cloudflare_named_setup.sh
# Helper to create a persistent Cloudflare named tunnel locally.
# Usage: ./cloudflare_named_setup.sh --name eddie-homelab

TUNNEL_NAME="eddie-homelab"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) TUNNEL_NAME="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--name <tunnel-name>]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

echo "1) Autenticar no Cloudflare (abrirá navegador):"
echo "   cloudflared login"
echo
echo "Execute agora: cloudflared login"
echo "Após login, volte aqui e pressione ENTER to continuar."
read -r

echo "2) Criando named tunnel: '$TUNNEL_NAME'"
cloudflared tunnel create "$TUNNEL_NAME"

CREDS_FILE=$(ls ~/.cloudflared/*.json 2>/dev/null | tail -n1 || true)
if [ -z "$CREDS_FILE" ]; then
  echo "Arquivo de credenciais não encontrado em ~/.cloudflared. Verifique a criação do túnel." >&2
  exit 1
fi

echo "Created credentials: $CREDS_FILE"

CFG_YML="./cloudflared-${TUNNEL_NAME}-config.yml"
cat > "$CFG_YML" <<EOF
tunnel: ${TUNNEL_NAME}
credentials-file: $CREDS_FILE

ingress:
  - hostname: eddie.example.com
    service: http://localhost:3000
  - service: http_status:404
EOF

echo
echo "Config template written to: $CFG_YML"
echo "Adjust 'hostname' to your domain (or remove ingress + use DNS routes)."
echo
echo "Next steps (on your machine):"
echo " - Copy the credentials file and config to the homelab:"
echo "   scp $CREDS_FILE user@192.168.15.2:/tmp/"
echo "   scp $CFG_YML user@192.168.15.2:/tmp/"
echo " - On homelab, move to /etc/cloudflared/, set ownership and enable systemd unit:"
echo "   sudo mkdir -p /etc/cloudflared"
echo "   sudo mv /tmp/$(basename $CREDS_FILE) /etc/cloudflared/"
echo "   sudo mv /tmp/$(basename $CFG_YML) /etc/cloudflared/config.yml"
echo " - Start the tunnel via systemd:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now cloudflared-named@${TUNNEL_NAME}.service"

echo
echo "If you want, use tools/tunnels/deploy_named_tunnel_via_ssh.sh to copy files automatically."

exit 0
