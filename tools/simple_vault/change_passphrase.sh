#!/usr/bin/env bash
set -euo pipefail
# Usage: ./change_passphrase.sh OLD_PASSPHRASE NEW_PASSPHRASE
# If OLD_PASSPHRASE is empty, attempts to read recovered_passphrases.txt

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SECRETS_DIR="$SCRIPT_DIR/secrets"
RECOVERED="$SCRIPT_DIR/recovered_passphrases.txt"

if [ "$#" -lt 1 ]; then
  echo "Uso: $0 NEW_PASSPHRASE [OLD_PASSPHRASE]"
  exit 2
fi
NEW_PASS="$1"
OLD_PASS=""
if [ "$#" -ge 2 ]; then
  OLD_PASS="$2"
fi

if [ -z "$OLD_PASS" ]; then
  if [ -f "$RECOVERED" ]; then
    # try to extract first passphrase-looking line
    OLD_PASS=$(sed -n 's/^Found passphrase://p; s/^\s*\([A-Za-z0-9@#%_-]\{8,\}\)\s*$/\1/p' "$RECOVERED" | sed -n '1p' || true)
  fi
fi

if [ -z "$OLD_PASS" ]; then
  echo "Old passphrase not provided and not found in $RECOVERED" >&2
  exit 2
fi

echo "Will re-encrypt files in $SECRETS_DIR"

TMPDIR=$(mktemp -d)
OLD_PASSFILE="$TMPDIR/old_pass.txt"
NEW_PASSFILE="$TMPDIR/new_pass.txt"
printf "%s" "$OLD_PASS" > "$OLD_PASSFILE"
printf "%s" "$NEW_PASS" > "$NEW_PASSFILE"
chmod 600 "$OLD_PASSFILE" "$NEW_PASSFILE"

failures=()
for g in "$SECRETS_DIR"/*.gpg; do
  [ -e "$g" ] || continue
  echo "Processing $(basename "$g")"
  base="${g%.gpg}"
  tmp_plain="$TMPDIR/$(basename "$base")"

  # If file already decrypts with NEW pass, assume migrated
  if gpg --quiet --batch --yes --passphrase-file "$NEW_PASSFILE" -o /dev/null -d "$g" 2>/dev/null; then
    echo " - already uses new passphrase; skipping"
    continue
  fi

  # Try decrypt with OLD pass
  if ! gpg --quiet --batch --yes --passphrase-file "$OLD_PASSFILE" -o "$tmp_plain" -d "$g"; then
    echo "Warning: Failed to decrypt $g with old passphrase; skipping" >&2
    failures+=("$g:decrypt")
    continue
  fi

  # backup original
  cp -a "$g" "$g.bak"

  # re-encrypt with new passphrase
  if ! gpg --quiet --batch --yes --passphrase-file "$NEW_PASSFILE" --symmetric --cipher-algo AES256 -o "$g" "$tmp_plain"; then
    echo "Warning: Failed to encrypt $g with new passphrase; restoring backup" >&2
    mv -f "$g.bak" "$g" || true
    rm -f "$tmp_plain"
    failures+=("$g:encrypt")
    continue
  fi

  rm -f "$tmp_plain"
  echo "Re-encrypted $(basename "$g")"
done

if [ ${#failures[@]} -ne 0 ]; then
  echo "Some files failed to migrate:" >&2
  for f in "${failures[@]}"; do echo " - $f" >&2; done
else
  echo "All .gpg files processed successfully."
fi

# write new canonical passphrase file
CANONICAL="$SCRIPT_DIR/passphrase"
printf "%s" "$NEW_PASS" > "$CANONICAL"
chmod 600 "$CANONICAL"

rm -rf "$TMPDIR"
echo "Done. New passphrase written to $CANONICAL and backups created as *.gpg.bak"
