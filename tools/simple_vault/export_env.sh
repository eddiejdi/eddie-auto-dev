#!/usr/bin/env bash
# Export secrets from tools/simple_vault/secrets to stdout as `export VAR=value` lines
# Usage: sudo SYSTEMD_UNIT=eddie-calendar.service bash tools/simple_vault/export_env.sh > /etc/default/eddie-calendar

set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SECRETS_DIR="$REPO_DIR/tools/simple_vault/secrets"
PASSPHRASE_FILE="$REPO_DIR/tools/simple_vault/passphrase"

if [[ ! -f "$PASSPHRASE_FILE" ]]; then
  echo "Passphrase file not found: $PASSPHRASE_FILE" >&2
  exit 1
fi

decrypt_to_stdout() {
  local file="$1"
  if [[ -f "$file" ]]; then
    gpg --quiet --batch --yes --passphrase-file "$PASSPHRASE_FILE" -d "$file" 2>/dev/null || return 1
  fi
}

# Map secret files to environment names
# Add mappings here as needed
declare -A MAP=(
  [telegram_bot_token.gpg]=TELEGRAM_BOT_TOKEN
  [telegram_chat_id.gpg]=TELEGRAM_CHAT_ID
  [fly_api_token.gpg]=FLY_API_TOKEN
)

for f in "${!MAP[@]}"; do
  path="$SECRETS_DIR/$f"
  varname="${MAP[$f]}"
  if [[ -f "$path" ]]; then
    val=$(decrypt_to_stdout "$path" ) || continue
    # shellcheck disable=SC2001
    safe=$(echo "$val" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    echo "export $varname=\"$safe\""
  fi
done
