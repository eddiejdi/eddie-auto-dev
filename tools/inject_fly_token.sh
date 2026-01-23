#!/usr/bin/env bash
# Inject FLY_API_TOKEN from tools/simple_vault/secrets/fly_api_token.txt into env files
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
TOKEN_FILE="$REPO_DIR/tools/simple_vault/secrets/fly_api_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
  echo "Token file not found: $TOKEN_FILE" >&2
  exit 2
fi
TOKEN=$(sed -n '1p' "$TOKEN_FILE" | tr -d '\n')
if [ -z "$TOKEN" ]; then
  echo "Token file is empty" >&2
  exit 3
fi
echo "Using token from $TOKEN_FILE (first 8 chars: ${TOKEN:0:8}...)"

FILES=(
  "$REPO_DIR/deploy/production_autonomous.env"
  "$REPO_DIR/deploy/production_remediator.env.example"
  "$REPO_DIR/tools/systemd/autonomous_remediator.env.example"
)

for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    echo "Patching $f"
    sed -i "/^FLY_API_TOKEN=/d" "$f" || true
    echo "FLY_API_TOKEN=$TOKEN" >> "$f"
  else
    echo "Creating and writing $f"
    mkdir -p "$(dirname "$f")"
    echo "FLY_API_TOKEN=$TOKEN" > "$f"
  fi
done

echo "Injection complete. Please secure $TOKEN_FILE (chmod 600) and restart services if needed." 
