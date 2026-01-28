#!/usr/bin/env bash
set -euo pipefail
# Push secrets from tools/simple_vault/secrets to the current GitHub repository using `gh`.
# Usage: ./push_secrets_to_github.sh [--apply]
# By default runs in dry-run mode and prints which secrets would be set.

REPO_ARG=""
APPLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --repo) REPO_ARG="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

SECRETS_DIR="$(dirname "$0")/secrets"
if [ ! -d "$SECRETS_DIR" ]; then
  echo "Secrets dir not found: $SECRETS_DIR" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install and authenticate 'gh' first." >&2
  exit 1
fi

if [ -z "$REPO_ARG" ]; then
  REPO_JSON=$(gh repo view --json nameWithOwner 2>/dev/null || true)
  if [ -z "$REPO_JSON" ]; then
    echo "Unable to detect repo with 'gh repo view'. Use --repo owner/name" >&2
    exit 1
  fi
  REPO=$(echo "$REPO_JSON" | sed -n 's/.*"nameWithOwner": "\([^"]\+\)".*/\1/p')
else
  REPO="$REPO_ARG"
fi

echo "Target repo: $REPO"
echo "Secrets dir: $SECRETS_DIR"
echo

for f in "$SECRETS_DIR"/*; do
  [ -f "$f" ] || continue
  ext="${f##*.}"
  base="$(basename "$f")"
  # Only push plain text files; skip .gpg files
  if [ "$ext" != "txt" ]; then
    echo "Skipping $base (unsupported extension: $ext)"
    continue
  fi

  name_upper=$(echo "$base" | tr '[:lower:].' '[:upper:]_' | sed 's/\.TXT$//' )
  value=$(sed ':a;N;$!ba;s/\n$//' "$f")

  echo "Will set secret: $name_upper (from $base)"
  if [ $APPLY -eq 1 ]; then
    echo "Setting secret $name_upper..."
    echo -n "$value" | gh secret set "$name_upper" --body - --repo "$REPO"
    echo "OK"
  fi
done

if [ $APPLY -eq 0 ]; then
  echo
  echo "Dry run complete. To actually apply secrets run with --apply"
fi
