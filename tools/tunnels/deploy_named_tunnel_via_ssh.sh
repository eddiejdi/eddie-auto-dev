#!/usr/bin/env bash
set -euo pipefail

# deploy_named_tunnel_via_ssh.sh
# Copies Cloudflare named tunnel credentials and config to a remote host and enables systemd.
# Usage: ./deploy_named_tunnel_via_ssh.sh --host ${HOMELAB_HOST} --user homelab --tunnel eddie-homelab 

HOST=""
USER=""
TUNNEL="eddie-homelab"
CREDS_FILE=""
CONFIG_FILE=""
CREDS_SECRET=""
CONFIG_SECRET=""

usage(){
  echo "Usage: $0 --host <host> --user <user> --tunnel <tunnel-name> --creds <creds.json> --config <config.yml>" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --tunnel) TUNNEL="$2"; shift 2 ;;
    --creds) CREDS_FILE="$2"; shift 2 ;;
    --config) CONFIG_FILE="$2"; shift 2 ;;
    --creds-secret) CREDS_SECRET="$2"; shift 2 ;;
    --config-secret) CONFIG_SECRET="$2"; shift 2 ;;
    --no-validate) NO_VALIDATE=1; shift 1 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

if [ -z "$HOST" ] || [ -z "$USER" ]; then
  usage
fi

# If secrets are provided, fetch them via tools/vault/secret_store.py
TMP_CREDS=""
TMP_CONFIG=""
cleanup_tmp() {
  [ -n "$TMP_CREDS" ] && rm -f "$TMP_CREDS" || true
  [ -n "$TMP_CONFIG" ] && rm -f "$TMP_CONFIG" || true
}
trap cleanup_tmp EXIT

if [ -n "$CREDS_SECRET" ] && [ -z "$CREDS_FILE" ]; then
  echo "Obtendo credenciais do agent secret: $CREDS_SECRET"
  TMP_CREDS=$(mktemp)
  if ! python3 tools/vault/secret_store.py get "$CREDS_SECRET" > "$TMP_CREDS" 2>/dev/null; then
    echo "Falha ao obter secret '$CREDS_SECRET'" >&2
    exit 1
  fi
  CREDS_FILE="$TMP_CREDS"
fi

if [ -n "$CONFIG_SECRET" ] && [ -z "$CONFIG_FILE" ]; then
  echo "Obtendo config do agent secret: $CONFIG_SECRET"
  TMP_CONFIG=$(mktemp)
  if ! python3 tools/vault/secret_store.py get "$CONFIG_SECRET" > "$TMP_CONFIG" 2>/dev/null; then
    echo "Falha ao obter secret '$CONFIG_SECRET'" >&2
    exit 1
  fi
  CONFIG_FILE="$TMP_CONFIG"
fi

if [ -z "$CREDS_FILE" ] || [ -z "$CONFIG_FILE" ]; then
  echo "Erro: é necessário informar --creds/--creds-secret e --config/--config-secret" >&2
  usage
fi

# Optional validation of credential (JSON) and config (YAML) files
: ${NO_VALIDATE:=0}
if [ "$NO_VALIDATE" -eq 0 ]; then
  echo "Validando arquivos antes do deploy..."
  # Validate creds: must be valid JSON (cloudflared credential file is JSON)
  if command -v python3 &> /dev/null; then
    if ! python3 -c "import sys,json; json.load(open('$CREDS_FILE'))" 2>/dev/null; then
      echo "Erro: arquivo de credenciais '$CREDS_FILE' não é JSON válido." >&2
      exit 1
    fi
  else
    if ! grep -q '{' "$CREDS_FILE"; then
      echo "Aviso: não foi possível validar JSON (python3 ausente). O arquivo '$CREDS_FILE' parece inválido." >&2
      exit 1
    fi
  fi

  # Validate config: try YAML parsing via python3+PyYAML, fallback to basic checks
  if command -v python3 &> /dev/null; then
    python3 - <<PYCODE 2>/dev/null
import sys
try:
    import yaml
except Exception:
    yaml=None
if yaml:
    try:
        yaml.safe_load(open('$CONFIG_FILE'))
    except Exception as e:
        print('Erro: config.yml inválido:', e, file=sys.stderr); sys.exit(1)
else:
    # basic heuristic: require at least one of these keywords
    with open('$CONFIG_FILE') as f:
        s = f.read()
    if not any(k in s for k in ('tunnel', 'ingress', 'url', 'hostname')):
        print('Aviso: não foi possível validar YAML (PyYAML ausente) e o arquivo parece incompleto.', file=sys.stderr); sys.exit(1)
PYCODE
  else
    if ! grep -E -q 'tunnel|ingress|url|hostname' "$CONFIG_FILE"; then
      echo "Aviso: python3 ausente; arquivo de config parece incompleto." >&2
      exit 1
    fi
  fi
fi

REMOTE_DIR="/etc/cloudflared"

echo "Copying credentials and config to ${USER}@${HOST}..."
scp "$CREDS_FILE" "${USER}@${HOST}:/tmp/" 
scp "$CONFIG_FILE" "${USER}@${HOST}:/tmp/"

echo "Moving files into place and setting permissions..."
ssh "${USER}@${HOST}" sudo mkdir -p "$REMOTE_DIR"
ssh "${USER}@${HOST}" sudo mv "/tmp/$(basename "$CREDS_FILE")" "$REMOTE_DIR/"
ssh "${USER}@${HOST}" sudo mv "/tmp/$(basename "$CONFIG_FILE")" "$REMOTE_DIR/config.yml"
ssh "${USER}@${HOST}" sudo chown root:root "$REMOTE_DIR/$(basename "$CREDS_FILE")" "$REMOTE_DIR/config.yml"
ssh "${USER}@${HOST}" sudo chmod 640 "$REMOTE_DIR/$(basename "$CREDS_FILE")" "$REMOTE_DIR/config.yml"

echo "Installing systemd unit for named tunnel and starting service..."
scp ./cloudflared-named@.service "${USER}@${HOST}:/tmp/cloudflared-named@.service"
ssh "${USER}@${HOST}" sudo mv /tmp/cloudflared-named@.service /etc/systemd/system/cloudflared-named@.service
ssh "${USER}@${HOST}" sudo systemctl daemon-reload
ssh "${USER}@${HOST}" sudo systemctl enable --now cloudflared-named@${TUNNEL}.service

echo "Deployed named tunnel '${TUNNEL}' to ${HOST}. Check:"
echo "  ssh ${USER}@${HOST} 'sudo systemctl status cloudflared-named@${TUNNEL}.service'"

exit 0
