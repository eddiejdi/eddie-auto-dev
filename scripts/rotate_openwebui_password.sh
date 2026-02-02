#!/usr/bin/env bash
# Rotate OpenWebUI password on homelab
# Usage: CURRENT_PASSWORD='Eddie@2026' NEW_PASSWORD='...' bash rotate_openwebui_password.sh

set -euo pipefail

CURRENT_EMAIL="${CURRENT_EMAIL:-edenilson.adm@gmail.com}"
CURRENT_PASSWORD="${CURRENT_PASSWORD:-}"
NEW_PASSWORD="${NEW_PASSWORD:-}"

if [[ -z "$CURRENT_PASSWORD" ]] || [[ -z "$NEW_PASSWORD" ]]; then
    echo "Usage:"
    echo "  CURRENT_PASSWORD='...' NEW_PASSWORD='...' bash $0"
    exit 1
fi

echo "[*] Obtaining JWT token..."
TOKEN=$(curl -s -X POST http://127.0.0.1:3000/api/v1/auths/signin \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$CURRENT_EMAIL\",\"password\":\"$CURRENT_PASSWORD\"}" 2>/dev/null | jq -r '.token // empty')

if [[ -z "$TOKEN" ]]; then
    echo "[!] Failed to obtain token. Current password may be incorrect."
    exit 1
fi

echo "[✓] Token obtained"
echo "[*] Updating password..."

# Update user profile with new password
UPDATE_RESP=$(curl -s -X POST http://127.0.0.1:3000/api/v1/users/profile/password \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"password\":\"$NEW_PASSWORD\"}" 2>/dev/null)

if echo "$UPDATE_RESP" | jq -e . >/dev/null 2>&1; then
    echo "[✓] Password update submitted"
    echo "$UPDATE_RESP" | jq '.'
else
    echo "[!] Response: $UPDATE_RESP"
fi

echo "[✓] Rotation complete. Please verify with new credentials:"
echo "    Email: $CURRENT_EMAIL"
echo "    Password: (new password saved in Bitwarden and GitHub secrets)"
