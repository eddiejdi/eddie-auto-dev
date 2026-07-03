#!/usr/bin/env bash
# Configura o TrueNAS SCALE como cliente LDAP do Authentik.
# Lê credenciais do secrets agent — nunca hardcode aqui.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_ENV="${HOME}/.config/homelab/secrets.env"

if [[ -f "$SECRETS_ENV" ]]; then
  # shellcheck source=/dev/null
  source "$SECRETS_ENV"
fi

if [[ -z "${SECRETS_AGENT_API_KEY:-}" ]]; then
  echo "[erro] SECRETS_AGENT_API_KEY não encontrada. Verifique ${SECRETS_ENV}" >&2
  exit 1
fi

export SECRETS_AGENT_API_KEY
export AUTHENTIK_URL="${AUTHENTIK_URL:-http://192.168.15.2:9000}"
export NAS_URL="${NAS_URL:-http://192.168.15.4}"

APPLY="${1:-}"

if [[ "$APPLY" == "--apply" ]]; then
  echo "[*] Aplicando integração NAS → Authentik LDAP..."
  python3 "${SCRIPT_DIR}/configure_authentik_nas_ldap.py" --apply
else
  echo "[*] Dry-run (passe --apply para efetivar):"
  python3 "${SCRIPT_DIR}/configure_authentik_nas_ldap.py"
fi
