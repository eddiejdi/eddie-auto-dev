#!/usr/bin/env bash
# Simple helper to encrypt a secret file with GPG symmetric encryption.
# Usage: ./encrypt_secret.sh secrets/openwebui_api.key secrets/openwebui_api.key.gpg /path/to/passphrase.txt

set -euo pipefail

IN="$1"
OUT="$2"
PASSFILE="$3"

if [ ! -f "$IN" ]; then
  echo "Input file not found: $IN" >&2
  exit 2
fi
if [ ! -f "$PASSFILE" ]; then
  echo "Passphrase file not found: $PASSFILE" >&2
  exit 2
fi

gpg --quiet --batch --yes --passphrase-file "$PASSFILE" \
    --symmetric --cipher-algo AES256 -o "$OUT" "$IN"

echo "Encrypted $IN -> $OUT"
