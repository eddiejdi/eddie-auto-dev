#!/usr/bin/env bash
set -euo pipefail

# deploy_public_server.sh
# Usage: sudo ./deploy_public_server.sh <PUBLIC_DOMAIN> [SITE_ROOT]
# Run this on the PUBLIC server (the one that will host openwebui.rpa4al.com or the site).

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <PUBLIC_DOMAIN> [SITE_ROOT]"
  exit 2
fi

DOMAIN=$1
SITE_ROOT=${2:-/var/www/rpa4al/site}
NGINX_SITE_CONF="/etc/nginx/sites-available/openwebui.conf"

echo "[1/7] Installing nginx and certbot (if not present)..."
if ! command -v nginx >/dev/null 2>&1; then
  apt-get update
  apt-get install -y nginx
fi

if ! command -v certbot >/dev/null 2>&1; then
  apt-get install -y certbot python3-certbot-nginx
fi

echo "[2/7] Creating Nginx site configuration for $DOMAIN..."
# Use the template in repo if present
REPO_CONF="$(pwd)/site/deploy/openwebui-nginx.conf"
if [ -f "$REPO_CONF" ]; then
  sudo cp "$REPO_CONF" "$NGINX_SITE_CONF"
  sudo sed -i "s/server_name openwebui.rpa4al.com;/server_name ${DOMAIN};/" "$NGINX_SITE_CONF"
else
  echo "Nginx template not found in repo. Please copy site/deploy/openwebui-nginx.conf to $NGINX_SITE_CONF and update server_name."; exit 1
fi

sudo ln -sf "$NGINX_SITE_CONF" /etc/nginx/sites-enabled/openwebui.conf

echo "[3/7] Testing and reloading Nginx..."
sudo nginx -t
sudo systemctl reload nginx

echo "[4/7] Make sure $SITE_ROOT exists (for the main site) and has index.html..."
sudo mkdir -p "$SITE_ROOT"
sudo chown -R $USER:$USER "$SITE_ROOT"

echo "[5/7] Obtaining TLS certificate via certbot..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@${DOMAIN} || echo "Certbot failed - run manually to troubleshoot"

echo "[6/7] Firewall: open HTTP/HTTPS (if using ufw)..."
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 'Nginx Full'
fi

echo "[7/7] Done. Verify with: curl -I https://${DOMAIN}/ and check headers. Ensure the homelab created an SSH reverse tunnel to 127.0.0.1:13300 so Nginx can proxy to it."
