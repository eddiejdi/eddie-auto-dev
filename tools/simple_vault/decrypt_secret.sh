#!/usr/bin/env bash
# Simple helper to decrypt a gpg symmetric file to stdout or file.
# Usage: ./decrypt_secret.sh secrets/openwebui_api.key.gpg /path/to/passphrase.txt /tmp/openwebui_api.key

set -euo pipefail

IN="$1"
PASSFILE="$2"
OUT="${3:-}" 

if [ ! -f "$IN" ]; then
  echo "Input file not found: $IN" >&2
  exit 2
fi
if [ ! -f "$PASSFILE" ]; then
  echo "Passphrase file not found: $PASSFILE" >&2
  exit 2
fi

if [ -z "$OUT" ]; then
  gpg --quiet --batch --yes --passphrase-file "$PASSFILE" -d "$IN"
else
  gpg --quiet --batch --yes --passphrase-file "$PASSFILE" -o "$OUT" -d "$IN"
  echo "Decrypted $IN -> $OUT"
fi
