#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="tools/simple_vault/secrets"
PASSPH_FILE="${SIMPLE_VAULT_PASSPHRASE_FILE:-tools/simple_vault/passphrase.txt}"
REPORT="/tmp/simple_vault_migration_report.$$.txt"
TMPDIR=$(mktemp -d)

echo "Migration started at $(date)" > "$REPORT"

if ! command -v bw >/dev/null 2>&1; then
  echo "bw CLI not found. Install and try again." >&2
  exit 2
fi

# Ensure bw unlocked
if ! bw login --check >/dev/null 2>&1; then
  echo "Por favor faça bw login antes de executar este script." >&2
  exit 2
fi

export BW_SESSION
BW_SESSION="$(bw unlock --raw)"
export BW_SESSION

count_ok=0
count_fail=0

for g in "$SECRETS_DIR"/*.gpg; do
  [ -e "$g" ] || continue
  name=$(basename "$g" .gpg)
  tmp_plain="$TMPDIR/$name.txt"
  tmp_json="$TMPDIR/$name.json"

  # Try decrypt with passphrase file if it exists, else fall back to interactive gpg
  if [ -f "$PASSPH_FILE" ]; then
    if ! gpg --quiet --batch --yes --passphrase-file "$PASSPH_FILE" -o "$tmp_plain" -d "$g" 2>/dev/null; then
      echo "$name: DECRYPT_FAIL (with passphrase file)" >> "$REPORT"
      count_fail=$((count_fail+1))
      rm -f "$tmp_plain" || true
      continue
    fi
  else
    # Interactive decryption (may prompt)
    if ! gpg --quiet -o "$tmp_plain" -d "$g" 2>/dev/null; then
      echo "$name: DECRYPT_FAIL (interactive)" >> "$REPORT"
      count_fail=$((count_fail+1))
      rm -f "$tmp_plain" || true
      continue
    fi
  fi

  # Build a minimal Bitwarden item JSON (type 2 - secure note) containing the secret in a field named "secret"
  secret_content=$(printf '%s' "$(cat "$tmp_plain")")
  jq -n --arg n "$name" --arg s "$secret_content" '{type:2,name:$n,notes:("Migrated from simple_vault: " + $n),fields:[{name:"secret",value:$s,type:1}]}' > "$tmp_json"

  # Create item in BW, suppress stdout/stderr to avoid leaking secrets in logs; check exit status
  if bw encode < "$tmp_json" | bw create item >/dev/null 2>&1; then
    echo "$name: OK" >> "$REPORT"
    count_ok=$((count_ok+1))
  else
    echo "$name: CREATE_FAIL" >> "$REPORT"
    count_fail=$((count_fail+1))
  fi

  # cleanup
  shred -u "$tmp_plain" 2>/dev/null || rm -f "$tmp_plain" || true
  shred -u "$tmp_json" 2>/dev/null || rm -f "$tmp_json" || true

done

bw sync >/dev/null 2>&1 || true

echo "Migration finished at $(date)" >> "$REPORT"
echo "OK: $count_ok, FAIL: $count_fail" >> "$REPORT"

# Print report summary (names and statuses) without secret contents
cat "$REPORT"
rm -rf "$TMPDIR"
unset BW_SESSION
exit 0
