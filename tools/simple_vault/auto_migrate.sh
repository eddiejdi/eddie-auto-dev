#!/usr/bin/env bash
# Orchestrate migration from Vaultwarden to simple GPG vault
# Usage: ./auto_migrate.sh [--apply-systemd] [--passphrase-file /path/to/passphrase] [--yes]

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
SECRETS_DIR="$SCRIPT_DIR/secrets"
PASSFILE_DEFAULT="$SCRIPT_DIR/passphrase"
MAP_FILE="$REPO_ROOT/tools/vault/secret_map.json"
ARCHIVE="$SCRIPT_DIR/vaultwarden_archive_$(date +%Y%m%d%H%M%S).tar.gz"

APPLY_SYSTEMD=0
PASSFILE=""
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply-systemd) APPLY_SYSTEMD=1; shift ;;
    --passphrase-file) PASSFILE="$2"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    *) echo "Unknown arg $1"; exit 2 ;;
  esac
done

if [ -z "$PASSFILE" ]; then
  if [ -f "$PASSFILE_DEFAULT" ]; then
    PASSFILE="$PASSFILE_DEFAULT"
  fi
fi

mkdir -p "$SECRETS_DIR"

echo "Archiving existing Vaultwarden folder if present..."
if [ -d "$REPO_ROOT/tools/vaultwarden_disabled" ]; then
  tar -czf "$ARCHIVE" -C "$REPO_ROOT/tools" vaultwarden_disabled
  echo "Archived tools/vaultwarden_disabled -> $ARCHIVE"
else
  echo "No tools/vaultwarden_disabled folder found; skipping archive"
fi

echo "Checking secret map: $MAP_FILE"
if [ ! -f "$MAP_FILE" ]; then
  echo "Secret map not found: $MAP_FILE" >&2
  exit 1
fi

missing=()
while IFS= read -r line; do
  # crude JSON parse for item names
  item=$(echo "$line" | sed -n 's/.*"item"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p')
  if [ -n "$item" ]; then
    fname=$(echo "$item" | tr '/ ' '__')
    gfile="$SECRETS_DIR/${fname}.gpg"
    if [ -f "$gfile" ]; then
      echo "FOUND: $item -> $gfile"
    else
      echo "MISSING: $item (expected $gfile)"
      missing+=("$item")
    fi
  fi
done < <(sed -n '1,200p' "$MAP_FILE")

echo
echo "Summary: $((${#missing[@]})) items missing, $(($(jq '.|length' "$MAP_FILE" 2>/dev/null || echo 0)-${#missing[@]})) present"

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing items:"
  for i in "${missing[@]}"; do echo " - $i"; done
fi

if [ "$APPLY_SYSTEMD" -eq 1 ]; then
  if [ "$ASSUME_YES" -ne 1 ]; then
    echo "--apply-systemd requested but not --yes; aborting before changing systemd units." >&2
    exit 2
  fi
  if [ "$EUID" -ne 0 ]; then
    echo "Applying systemd changes requires root. Re-run with sudo." >&2
    exit 2
  fi
  # create global env file
  ENVFILE="/etc/default/simple_vault"
  echo "SIMPLE_VAULT_PASSPHRASE_FILE=${PASSFILE:-$PASSFILE_DEFAULT}" > "$ENVFILE"
  echo "Wrote $ENVFILE"
  # patch common units (dry list from repo)
  units=(open-webui.service btc-webui-api.service eddie-telegram-bot.service)
  for u in "${units[@]}"; do
    dropdir="/etc/systemd/system/${u}.d"
    mkdir -p "$dropdir"
    cat > "$dropdir/override.conf" <<EOF
[Service]
EnvironmentFile=$ENVFILE
EOF
    echo "Patched $u with EnvironmentFile"
  done
  systemctl daemon-reload || true
  echo "systemd daemon-reloaded. You may restart services as needed."
fi

echo "Done."
