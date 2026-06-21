#!/usr/bin/env bash
# Publica o CMDB atras do Authentik em auth.rpa4all.com/cmdb/.

set -euo pipefail

SSH_USER="homelab"
SSH_HOST="192.168.15.2"
SSH_KEY="${HOME}/.ssh/homelab_key"
REMOTE_REPO="/home/${SSH_USER}/eddie-auto-dev"
REMOTE_RUNTIME_DIR="/home/${SSH_USER}/cmdb"
REMOTE_NGINX_AUTH="/etc/nginx/sites-available/auth.rpa4all.com"
REMOTE_NGINX_AUTH_ENABLED="/etc/nginx/sites-enabled/auth.rpa4all.com"
REMOTE_NGINX_AUTH_PUBLIC="/etc/nginx/sites-available/auth.rpa4all.com-public"
REMOTE_NGINX_AUTH_PUBLIC_ENABLED="/etc/nginx/sites-enabled/auth.rpa4all.com-public"
PUBLIC_PORTAL_URL="https://auth.rpa4all.com/cmdb/"
PUBLIC_NETBOX_URL="https://auth.rpa4all.com/cmdb/netbox/"
PUBLIC_GLPI_URL="https://auth.rpa4all.com/cmdb/glpi/index.php"

ssh_run() {
  ssh -i "$SSH_KEY" "${SSH_USER}@${SSH_HOST}" "$@"
}

remote_compose_cmd() {
  ssh_run '
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

echo "[1/7] Copiando artefatos do CMDB"
ssh_run "mkdir -p ${REMOTE_RUNTIME_DIR}"
scp -i "$SSH_KEY" -r deploy/cmdb/. "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" site/deploy/auth-cmdb-location.nginx.conf "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" site/deploy/auth-public-server.nginx.conf "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" site/cmdb/index.html "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" scripts/cmdb/configure_glpi_sso.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" scripts/cmdb/ensure_glpi_admin_users.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" scripts/misc/register_cmdb_authentik.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"
scp -i "$SSH_KEY" scripts/deployment/deploy_cmdb_auth.sh "${SSH_USER}@${SSH_HOST}:${REMOTE_RUNTIME_DIR}/"

echo "[2/7] Sincronizando runtime do CMDB"
ssh_run "python3 - ${REMOTE_RUNTIME_DIR}/.env <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
content = env_path.read_text(encoding='utf-8').splitlines()
values = {}
for line in content:
    if not line or line.lstrip().startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    values[key] = value

values.update({
    'NETBOX_ALLOWED_HOSTS': 'auth.rpa4all.com 192.168.15.2 localhost 127.0.0.1',
    'NETBOX_CSRF_TRUSTED_ORIGINS': 'https://auth.rpa4all.com',
    'NETBOX_BASE_PATH': 'cmdb/netbox/',
    'NETBOX_LOGIN_REQUIRED': 'true',
    'NETBOX_LOGOUT_REDIRECT_URL': 'https://auth.rpa4all.com/outpost.goauthentik.io/sign_out',
    'NETBOX_SKIP_SUPERUSER': 'true',
    'NETBOX_REMOTE_AUTH_ENABLED': 'true',
    'NETBOX_REMOTE_AUTH_AUTO_CREATE_USER': 'true',
    'NETBOX_REMOTE_AUTH_HEADER': 'HTTP_X_AUTHENTIK_USERNAME',
    'NETBOX_REMOTE_AUTH_USER_EMAIL': 'HTTP_X_AUTHENTIK_EMAIL',
    'NETBOX_REMOTE_AUTH_GROUP_SYNC_ENABLED': 'true',
    'NETBOX_REMOTE_AUTH_GROUP_HEADER': 'HTTP_X_AUTHENTIK_GROUPS',
    'NETBOX_REMOTE_AUTH_GROUP_SEPARATOR': '|',
    'NETBOX_REMOTE_AUTH_STAFF_GROUPS': 'authentik Admins',
    'NETBOX_REMOTE_AUTH_SUPERUSER_GROUPS': 'authentik Admins',
})

ordered_keys = []
seen = set()
for line in content:
    if not line or line.lstrip().startswith('#') or '=' not in line:
        continue
    key = line.split('=', 1)[0]
    if key not in seen:
        ordered_keys.append(key)
        seen.add(key)
for key in values:
    if key not in seen:
        ordered_keys.append(key)
        seen.add(key)

lines = [f'{key}={values[key]}' for key in ordered_keys]
env_path.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')
PY"

echo "[3/7] Recriando containers alterados"
ssh_run "
set -euo pipefail
cd ${REMOTE_RUNTIME_DIR}
docker rm -f cmdb-netbox cmdb-netbox-worker cmdb-glpi >/dev/null 2>&1 || true
${COMPOSE_CMD} --env-file .env -f docker-compose.yml up -d --no-deps netbox glpi
${COMPOSE_CMD} --env-file .env -f docker-compose.yml up -d --no-deps netbox-worker
for attempt in \$(seq 1 36); do
  if curl -fsS http://127.0.0.1:18091/cmdb/netbox/login/ >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
for attempt in \$(seq 1 24); do
  if curl -fsS http://127.0.0.1:18092/cmdb/glpi/index.php >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
curl -fsS http://127.0.0.1:18091/cmdb/netbox/login/ >/dev/null
curl -fsS http://127.0.0.1:18092/cmdb/glpi/index.php >/dev/null
"

echo "[4/7] Configurando SSO do GLPI"
ssh_run "bash ${REMOTE_RUNTIME_DIR}/configure_glpi_sso.sh --env-file ${REMOTE_RUNTIME_DIR}/.env"
ssh_run "bash ${REMOTE_RUNTIME_DIR}/ensure_glpi_admin_users.sh --env-file ${REMOTE_RUNTIME_DIR}/.env"

echo "[5/7] Publicando rota /cmdb/ no auth.rpa4all.com"
ssh_run "sudo mkdir -p /var/www/cmdb-auth && sudo cp ${REMOTE_RUNTIME_DIR}/index.html /var/www/cmdb-auth/index.html && sudo chown -R root:root /var/www/cmdb-auth"
ssh_run bash -s -- "${REMOTE_RUNTIME_DIR}" "${REMOTE_NGINX_AUTH}" "${REMOTE_NGINX_AUTH_ENABLED}" "${REMOTE_NGINX_AUTH_PUBLIC}" "${REMOTE_NGINX_AUTH_PUBLIC_ENABLED}" <<'EOF'
set -e
REMOTE_RUNTIME_DIR="$1"
TARGET="$2"
TARGET_ENABLED="$3"
PUBLIC_TARGET="$4"
PUBLIC_TARGET_ENABLED="$5"
SNIPPET_PATH="${REMOTE_RUNTIME_DIR}/auth-cmdb-location.nginx.conf"
PUBLIC_TEMPLATE_PATH="${REMOTE_RUNTIME_DIR}/auth-public-server.nginx.conf"

TMP_FILE=$(mktemp)
UPDATED=$(python3 - "$SNIPPET_PATH" "$TARGET" "$TMP_FILE" <<'PY'
from pathlib import Path
import sys

snippet_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
tmp_path = Path(sys.argv[3])

snippet = snippet_path.read_text(encoding="utf-8").rstrip() + "\n\n"
content = target_path.read_text(encoding="utf-8")
start_marker = "location = /cmdb {"
marker = "    location / {"

if marker not in content:
    raise SystemExit("marker not found in auth nginx config")

start = content.find(start_marker)
if start == -1:
    updated = content.replace(marker, snippet + marker, 1)
else:
    marker_index = content.find(marker, start)
    if marker_index == -1:
        raise SystemExit("final location marker not found after cmdb block")
    updated = content[:start].rstrip() + "\n\n" + snippet + content[marker_index:]

tmp_path.write_text(updated, encoding="utf-8")
print("changed" if updated != content else "unchanged")
PY
)
if [ "$UPDATED" = "changed" ]; then
  sudo cp "$TARGET" "${TARGET}.bak-$(date +%Y%m%d%H%M%S)"
  sudo mv "$TMP_FILE" "$TARGET"
else
  rm -f "$TMP_FILE"
fi

if [ -e "$TARGET_ENABLED" ] && [ ! -L "$TARGET_ENABLED" ]; then
  sudo cp "$TARGET_ENABLED" "/tmp/$(basename "$TARGET_ENABLED").bak-$(date +%Y%m%d%H%M%S)"
  sudo rm -f "$TARGET_ENABLED"
fi
sudo ln -sfn "$TARGET" "$TARGET_ENABLED"

sudo cp "$PUBLIC_TEMPLATE_PATH" "$PUBLIC_TARGET"

if [ -e "$PUBLIC_TARGET_ENABLED" ] && [ ! -L "$PUBLIC_TARGET_ENABLED" ]; then
  sudo cp "$PUBLIC_TARGET_ENABLED" "/tmp/$(basename "$PUBLIC_TARGET_ENABLED").bak-$(date +%Y%m%d%H%M%S)"
  sudo rm -f "$PUBLIC_TARGET_ENABLED"
fi
sudo ln -sfn "$PUBLIC_TARGET" "$PUBLIC_TARGET_ENABLED"

sudo nginx -t
sudo systemctl reload nginx
EOF

echo "[6/7] Registrando portal na biblioteca do Authentik"
ssh_run "bash ${REMOTE_RUNTIME_DIR}/register_cmdb_authentik.sh"

echo "[7/7] Validando saude local e superficie publica"
ssh_run "
set -euo pipefail
cd ${REMOTE_RUNTIME_DIR}
${COMPOSE_CMD} --env-file .env -f docker-compose.yml ps
curl -fsSI http://127.0.0.1:18091/cmdb/netbox/login/ | sed -n '1,12p'
printf '\n'
COOKIE=\$(mktemp)
curl -fsS -L -c \"\$COOKIE\" -b \"\$COOKIE\" -D /tmp/cmdb-glpi-sso.headers -o /tmp/cmdb-glpi-sso.body -H 'X-Authentik-Username: edenilson' -H 'X-Authentik-Email: edenilson.paschoa@rpa4all.com' -H 'X-Authentik-Name: Edenilson Paschoa' http://127.0.0.1:18092/cmdb/glpi/index.php >/dev/null
sed -n '1,20p' /tmp/cmdb-glpi-sso.headers
rm -f \"\$COOKIE\"
printf '\n'
curl -skI '${PUBLIC_PORTAL_URL}' | sed -n '1,12p'
printf '\n'
curl -skI '${PUBLIC_NETBOX_URL}' | sed -n '1,12p'
printf '\n'
curl -skI '${PUBLIC_GLPI_URL}' | sed -n '1,12p'
"

echo "Deploy concluido:"
echo "  ${PUBLIC_PORTAL_URL}"
echo "  ${PUBLIC_NETBOX_URL}"
echo "  ${PUBLIC_GLPI_URL}"
