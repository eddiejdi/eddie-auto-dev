#!/usr/bin/env bash
set -euo pipefail

# Usage: ./add_secret.sh <secret_name>
# Reads secret value from stdin (or you can pipe) and encrypts into
# tools/simple_vault/secrets/<secret_name>.gpg using the repo passphrase.

NAME=${1:-}
if [ -z "$NAME" ]; then
  echo "usage: $0 <secret_name>" >&2
  exit 2
fi

SECRETS_DIR=$(dirname "$0")/secrets
PLAIN="$SECRETS_DIR/${NAME}.txt"
GPGOUT="$SECRETS_DIR/${NAME}.gpg"
PASSFILE=$(dirname "$0")/passphrase

if [ ! -f "$PASSFILE" ]; then
  echo "passphrase file not found: $PASSFILE" >&2
  exit 2
fi

echo "Enter value for secret '$NAME' (stdin). End with EOF / Ctrl-D:" >&2
cat > "$PLAIN"

bash "$(dirname "$0")/encrypt_secret.sh" "$PLAIN" "$GPGOUT" "$PASSFILE"
rm -f "$PLAIN"
echo "Secret '$NAME' saved -> $GPGOUT"
