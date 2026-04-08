#!/usr/bin/env bash
# Deploy do ntopng e publicacao em auth.rpa4all.com com protecao Authentik.

set -euo pipefail

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
REMOTE_REPO="/home/${SSH_USER}/eddie-auto-dev"
REMOTE_RUNTIME_DIR="/home/${SSH_USER}/monitoring/ntopng"
REMOTE_NGINX_AUTH="/etc/nginx/sites-available/auth.rpa4all.com"
REMOTE_NGINX_AUTH_ENABLED="/etc/nginx/sites-enabled/auth.rpa4all.com"
PUBLIC_URL="https://auth.rpa4all.com/ntopng/"

remote_compose_cmd() {
    ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" '
set -e
if command -v docker-compose >/dev/null 2>&1; then
  printf "docker-compose"
elif docker compose version >/dev/null 2>&1; then
  printf "docker compose"
else
  exit 1
fi
'
}

COMPOSE_CMD="$(remote_compose_cmd)"

echo "[1/6] Copiando artefatos"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "mkdir -p ${REMOTE_REPO}/docker ${REMOTE_REPO}/site/deploy ${REMOTE_REPO}/scripts/misc ${REMOTE_REPO}/scripts/deployment ${REMOTE_RUNTIME_DIR}"
scp -i ~/.ssh/homelab_key docker/docker-compose.ntopng.yml "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/docker/"
scp -i ~/.ssh/homelab_key site/deploy/auth-ntopng-location.nginx.conf "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/site/deploy/"
scp -i ~/.ssh/homelab_key scripts/misc/register_ntopng_authentik.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/scripts/misc/"
scp -i ~/.ssh/homelab_key scripts/deployment/deploy_ntopng_auth.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/scripts/deployment/"

echo "[2/6] Preparando dados do ntopng"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sudo mkdir -p /var/lib/ntopng && sudo chown -R ${SSH_USER}:${SSH_USER} /var/lib/ntopng"

echo "[3/6] Subindo stack"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "COMPOSE_PROJECT_NAME=ntopng ${COMPOSE_CMD} -f ${REMOTE_REPO}/docker/docker-compose.ntopng.yml up -d"

echo "[4/6] Publicando rota /ntopng/ no auth.rpa4all.com"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" bash -s -- "${REMOTE_REPO}" "${REMOTE_NGINX_AUTH}" "${REMOTE_NGINX_AUTH_ENABLED}" <<'EOF'
set -e
REMOTE_REPO="$1"
TARGET="$2"
TARGET_ENABLED="$3"
SNIPPET_PATH="${REMOTE_REPO}/site/deploy/auth-ntopng-location.nginx.conf"

if ! sudo grep -q "location \^~ /ntopng/" "$TARGET"; then
  TMP_FILE=$(mktemp)
  python3 - "$SNIPPET_PATH" "$TARGET" "$TMP_FILE" <<'PY'
from pathlib import Path
import sys

snippet_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
tmp_path = Path(sys.argv[3])

snippet = snippet_path.read_text(encoding="utf-8").rstrip() + "\n\n"
content = target_path.read_text(encoding="utf-8")
marker = "    location / {"

if marker not in content:
    raise SystemExit("marker not found in auth nginx config")

tmp_path.write_text(content.replace(marker, snippet + marker, 1), encoding="utf-8")
PY
  sudo cp "$TARGET" "${TARGET}.bak-$(date +%Y%m%d%H%M%S)"
  sudo mv "$TMP_FILE" "$TARGET"
fi

if [ ! -L "$TARGET_ENABLED" ]; then
  if [ -e "$TARGET_ENABLED" ]; then
    sudo cp "$TARGET_ENABLED" "/tmp/$(basename "$TARGET_ENABLED").bak-$(date +%Y%m%d%H%M%S)"
    sudo rm -f "$TARGET_ENABLED"
  fi
  sudo ln -s "$TARGET" "$TARGET_ENABLED"
fi

sudo find /etc/nginx/sites-enabled -maxdepth 1 -type f -name 'auth.rpa4all.com.bak-*' -delete

sudo nginx -t
sudo systemctl reload nginx
EOF

echo "[5/6] Registrando app no Authentik"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "bash ${REMOTE_REPO}/scripts/misc/register_ntopng_authentik.sh"

echo "[6/6] Validando endpoints"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" '
set -e
docker ps --filter name=ntopng --format "table {{.Names}}\t{{.Status}}"
curl -fsSI http://127.0.0.1:8877/ntopng/ | sed -n "1,10p"
curl -sk "'"${PUBLIC_URL}"'" -D /tmp/ntopng_public.headers -o /tmp/ntopng_public.body
sed -n "1,12p" /tmp/ntopng_public.headers
'

PUBLIC_STATUS="$(ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sed -n '1{s/^HTTP\\/[0-9.]* //;s/ .*//;p;q}' /tmp/ntopng_public.headers")"
PUBLIC_LOCATION="$(ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sed -n 's/^location: //Ip' /tmp/ntopng_public.headers | head -n 1 | tr -d '\\r'")"

if [ "${PUBLIC_STATUS}" != "302" ]; then
  echo "Falha: rota publica retornou status ${PUBLIC_STATUS}, esperado 302" >&2
  exit 1
fi

case "${PUBLIC_LOCATION}" in
  https://auth.rpa4all.com/outpost.goauthentik.io/start*) ;;
  *)
    echo "Falha: location inesperado para rota publica: ${PUBLIC_LOCATION}" >&2
    exit 1
    ;;
esac

echo "Deploy concluido: ${PUBLIC_URL}"#!/usr/bin/env bash
# Deploy do ntopng e publicacao em auth.rpa4all.com com protecao Authentik.

set -euo pipefail

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
REMOTE_REPO="/home/${SSH_USER}/eddie-auto-dev"
REMOTE_RUNTIME_DIR="/home/${SSH_USER}/monitoring/ntopng"
REMOTE_NGINX_AUTH="/etc/nginx/sites-available/auth.rpa4all.com"
REMOTE_NGINX_AUTH_ENABLED="/etc/nginx/sites-enabled/auth.rpa4all.com"
PUBLIC_URL="https://auth.rpa4all.com/ntopng/"

remote_compose_cmd() {
    ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" '
set -e
if command -v docker-compose >/dev/null 2>&1; then
  printf "docker-compose"
elif docker compose version >/dev/null 2>&1; then
  printf "docker compose"
else
  exit 1
fi
'
}

COMPOSE_CMD="$(remote_compose_cmd)"

echo "[1/6] Copiando artefatos"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "mkdir -p ${REMOTE_REPO}/docker ${REMOTE_REPO}/site/deploy ${REMOTE_REPO}/scripts/misc ${REMOTE_REPO}/scripts/deployment ${REMOTE_RUNTIME_DIR}"
scp -i ~/.ssh/homelab_key docker/docker-compose.ntopng.yml "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/docker/"
scp -i ~/.ssh/homelab_key site/deploy/auth-ntopng-location.nginx.conf "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/site/deploy/"
scp -i ~/.ssh/homelab_key scripts/misc/register_ntopng_authentik.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/scripts/misc/"
scp -i ~/.ssh/homelab_key scripts/deployment/deploy_ntopng_auth.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_REPO}/scripts/deployment/"

echo "[2/6] Preparando dados do ntopng"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sudo mkdir -p /var/lib/ntopng && sudo chown -R ${SSH_USER}:${SSH_USER} /var/lib/ntopng"

echo "[3/6] Subindo stack"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "COMPOSE_PROJECT_NAME=ntopng ${COMPOSE_CMD} -f ${REMOTE_REPO}/docker/docker-compose.ntopng.yml up -d"

echo "[4/6] Publicando rota /ntopng/ no auth.rpa4all.com"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" bash -s -- "${REMOTE_REPO}" "${REMOTE_NGINX_AUTH}" "${REMOTE_NGINX_AUTH_ENABLED}" <<'EOF'
set -e
REMOTE_REPO="$1"
TARGET="$2"
TARGET_ENABLED="$3"
SNIPPET_PATH="${REMOTE_REPO}/site/deploy/auth-ntopng-location.nginx.conf"

if ! sudo grep -q "location \^~ /ntopng/" "$TARGET"; then
  TMP_FILE=$(mktemp)
  python3 - "$SNIPPET_PATH" "$TARGET" "$TMP_FILE" <<'PY'
from pathlib import Path
import sys

snippet_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
tmp_path = Path(sys.argv[3])

snippet = snippet_path.read_text(encoding="utf-8").rstrip() + "\n\n"
content = target_path.read_text(encoding="utf-8")
marker = "    location / {"

if marker not in content:
    raise SystemExit("marker not found in auth nginx config")

tmp_path.write_text(content.replace(marker, snippet + marker, 1), encoding="utf-8")
PY
  sudo cp "$TARGET" "${TARGET}.bak-$(date +%Y%m%d%H%M%S)"
  sudo mv "$TMP_FILE" "$TARGET"
fi

if [ ! -L "$TARGET_ENABLED" ]; then
  if [ -e "$TARGET_ENABLED" ]; then
    sudo cp "$TARGET_ENABLED" "/tmp/$(basename "$TARGET_ENABLED").bak-$(date +%Y%m%d%H%M%S)"
    sudo rm -f "$TARGET_ENABLED"
  fi
  sudo ln -s "$TARGET" "$TARGET_ENABLED"
fi

sudo find /etc/nginx/sites-enabled -maxdepth 1 -type f -name 'auth.rpa4all.com.bak-*' -delete

sudo nginx -t
sudo systemctl reload nginx
EOF

echo "[5/6] Registrando app no Authentik"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "bash ${REMOTE_REPO}/scripts/misc/register_ntopng_authentik.sh"

echo "[6/6] Validando endpoints"
ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" '
set -e
docker ps --filter name=ntopng --format "table {{.Names}}\t{{.Status}}"
curl -fsSI http://127.0.0.1:8877/ntopng/ | sed -n "1,10p"
curl -sk "'"${PUBLIC_URL}"'" -D /tmp/ntopng_public.headers -o /tmp/ntopng_public.body
sed -n "1,12p" /tmp/ntopng_public.headers
'

PUBLIC_STATUS="$(ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sed -n '1{s/^HTTP\\/[0-9.]* //;s/ .*//;p;q}' /tmp/ntopng_public.headers")"
PUBLIC_LOCATION="$(ssh -i ~/.ssh/homelab_key "${SSH_USER}@${SSH_HOST}" "sed -n 's/^location: //Ip' /tmp/ntopng_public.headers | head -n 1 | tr -d '\\r'")"

if [ "${PUBLIC_STATUS}" != "302" ]; then
  echo "Falha: rota publica retornou status ${PUBLIC_STATUS}, esperado 302" >&2
  exit 1
fi

case "${PUBLIC_LOCATION}" in
  https://auth.rpa4all.com/outpost.goauthentik.io/start*) ;;
  *)
    echo "Falha: location inesperado para rota publica: ${PUBLIC_LOCATION}" >&2
    exit 1
    ;;
esac

echo "Deploy concluido: ${PUBLIC_URL}"