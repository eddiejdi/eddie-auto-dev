#!/usr/bin/env bash
set -euo pipefail

# Deploy the test home page to the homelab webroot
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)/web/home_test"
REMOTE_USER="homelab"
REMOTE_HOST="192.168.15.2"
REMOTE_DIR="/var/www/rpa4all"

echo "Deploying ${SRC_DIR} to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
rsync -av --delete "${SRC_DIR}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

# fix ownership (optional) and reload nginx
ssh "${REMOTE_USER}@${REMOTE_HOST}" "sudo chown -R www-data:www-data ${REMOTE_DIR} || true && sudo systemctl reload nginx"

echo "Deploy complete. Visit: https://www.rpa4all.com to verify." 
