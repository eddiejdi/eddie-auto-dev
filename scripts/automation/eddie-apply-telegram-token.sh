#!/bin/bash
# Aplica novo token Telegram: systemd drop-ins + Authentik (via secrets agent).
# Uso: eddie-apply-telegram-token.sh <TOKEN>
#      eddie-apply-telegram-token.sh --token-file <path>   (compatível com {token_file} do rotate script)
set -euo pipefail

TOKEN=""
if [ "${1:-}" = "--token-file" ]; then
  TOKEN="$(cat "$2")"
elif [ "$#" -eq 1 ] && [ -n "${1:-}" ]; then
  TOKEN="$1"
else
  echo "Usage: $0 <TELEGRAM_BOT_TOKEN>"
  echo "       $0 --token-file <path>"
  exit 1
fi

# --- 1. Systemd drop-ins e env file (comportamento original) ---
sudo mkdir -p /etc/eddie
printf "TELEGRAM_BOT_TOKEN=%s\n" "$TOKEN" | sudo tee /etc/eddie/telegram.env > /dev/null
sudo chown root:root /etc/eddie/telegram.env
sudo chmod 600 /etc/eddie/telegram.env

SERVICES="eddie-telegram-bot eddie-expurgo eddie-calendar homelab-dashboard eddie-location"
for s in $SERVICES; do
  sudo mkdir -p /etc/systemd/system/${s}.service.d
  printf '[Service]\nEnvironmentFile=/etc/eddie/telegram.env\n' \
    | sudo tee /etc/systemd/system/${s}.service.d/override.conf > /dev/null
done

sudo systemctl daemon-reload
for s in $SERVICES; do
  sudo systemctl unmask  ${s}.service 2>/dev/null || true
  sudo systemctl enable --now ${s}.service 2>/dev/null || true
done
for s in $SERVICES; do
  systemctl --user unmask  ${s}.service 2>/dev/null || true
  systemctl --user enable --now ${s}.service 2>/dev/null || true
done

echo "[1/2] Systemd drop-ins aplicados."

# --- 2. Persistir no Authentik via secrets agent ---
SECRETS_AGENT_URL="${SECRETS_AGENT_URL:-http://localhost:8088}"

# Lê a API key do drop-in do systemd (fallback para env var)
if [ -z "${SECRETS_AGENT_API_KEY:-}" ]; then
  SECRETS_AGENT_API_KEY=$(
    grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' \
      /etc/systemd/system/secrets-agent.service.d/override.conf \
      /etc/systemd/system/secrets_agent.service.d/override.conf \
      2>/dev/null | head -1
  )
fi

if [ -z "${SECRETS_AGENT_API_KEY:-}" ]; then
  echo "AVISO: SECRETS_AGENT_API_KEY não encontrado — pulando Authentik." >&2
  exit 0
fi

_store() {
  local name="$1" field="$2"
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SECRETS_AGENT_URL}/secrets" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${SECRETS_AGENT_API_KEY}" \
    -d "{\"name\":\"${name}\",\"value\":\"${TOKEN}\",\"field\":\"${field}\"}")
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo "  OK ${name}#${field}"
  else
    echo "  FALHA ${name}#${field} (HTTP ${http_code})" >&2
    return 1
  fi
}

echo "[2/2] Persistindo token no Authentik..."
_store "authentik/eddie/telegram_bot_token" "password"
_store "authentik/eddie/telegram_bot_token" "token"
_store "shared/telegram_bot_token"          "password"
_store "shared/telegram_bot_token"          "token"

echo "Token aplicado e persistido no Authentik com sucesso."
