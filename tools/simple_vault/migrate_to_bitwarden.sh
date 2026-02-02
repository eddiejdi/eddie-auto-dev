#!/usr/bin/env bash
# Migrate secrets from simple_vault to Bitwarden
# Usage: BW_SESSION=xxx ./migrate_to_bitwarden.sh
# Or: ./migrate_to_bitwarden.sh (will prompt for login)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SECRETS_DIR="$SCRIPT_DIR/secrets"
LOG_FILE="$SCRIPT_DIR/bw_migration_log.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[-]${NC} $1"; }

# Check bw CLI
if ! command -v bw &>/dev/null; then
    err "Bitwarden CLI (bw) not found. Install it first."
    exit 1
fi

# Check session
if [[ -z "${BW_SESSION:-}" ]]; then
    warn "BW_SESSION not set. Attempting to unlock..."
    if bw status 2>/dev/null | grep -q '"status":"unauthenticated"'; then
        err "Not logged in. Run: bw login your-email@example.com"
        exit 1
    fi
    export BW_SESSION=$(bw unlock --raw 2>/dev/null) || {
        err "Failed to unlock. Please run: export BW_SESSION=\$(bw unlock --raw)"
        exit 1
    }
fi

log "Bitwarden session active"

# Secrets to migrate (name -> env var name)
declare -A SECRETS=(
    ["openwebui_api_key.txt"]="OpenWebUI API Key"
    ["fly_api_token.txt"]="Fly.io API Token"
    ["public_tunnel_url.txt"]="Public Tunnel URL"
)

# Initialize migration log
echo '{"migrated": [], "errors": [], "timestamp": "'$(date -Iseconds)'"}' > "$LOG_FILE"

migrate_secret() {
    local file="$1"
    local name="$2"
    local filepath="$SECRETS_DIR/$file"
    
    if [[ ! -f "$filepath" ]]; then
        warn "File not found: $filepath"
        return 1
    fi
    
    local content
    content=$(cat "$filepath")
    
    # Skip if content indicates removal
    if echo "$content" | grep -qi "REMOVED\|removed"; then
        warn "Skipping $file - already removed/migrated"
        return 0
    fi
    
    # Create Bitwarden secure note
    local item_json
    item_json=$(cat <<EOF
{
  "type": 2,
  "name": "$name",
  "notes": "$content",
  "secureNote": {"type": 0}
}
EOF
)
    
    # Encode and create
    local encoded
    encoded=$(echo "$item_json" | bw encode)
    
    if bw create item "$encoded" --session "$BW_SESSION" >/dev/null 2>&1; then
        log "Migrated: $name"
        # Update log
        jq --arg f "$file" --arg n "$name" '.migrated += [{"file": $f, "name": $n}]' "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
        return 0
    else
        err "Failed to migrate: $name"
        jq --arg f "$file" --arg n "$name" '.errors += [{"file": $f, "name": $n}]' "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
        return 1
    fi
}

# Also migrate the exposed credential from workflow
migrate_exposed_credential() {
    log "Migrating exposed OpenWebUI credential from workflow..."
    
    local item_json
    item_json=$(cat <<EOF
{
  "type": 1,
  "name": "OpenWebUI Homelab Signin (ROTATED)",
  "login": {
    "username": "edenilson.adm@gmail.com",
    "password": "Eddie@2026"
  },
  "notes": "EXPOSED in commit e293156fd40445cf6931b0879d2b39466e792415\nSource: .github/workflows/rotate-openwebui-api-key.yml\nStatus: PASSWORD MUST BE ROTATED - was exposed publicly\nMigrated: $(date -Iseconds)"
}
EOF
)
    
    local encoded
    encoded=$(echo "$item_json" | bw encode)
    
    if bw create item "$encoded" --session "$BW_SESSION" >/dev/null 2>&1; then
        log "Migrated exposed credential (marked for rotation)"
        return 0
    else
        err "Failed to migrate exposed credential"
        return 1
    fi
}

# Main migration
log "Starting migration from simple_vault to Bitwarden..."
echo

for file in "${!SECRETS[@]}"; do
    migrate_secret "$file" "${SECRETS[$file]}" || true
done

# Migrate the exposed credential
migrate_exposed_credential || true

echo
log "Migration complete. Log saved to: $LOG_FILE"
log "Syncing Bitwarden..."
bw sync --session "$BW_SESSION" >/dev/null 2>&1 || warn "Sync failed"

echo
warn "IMPORTANT: Rotate the OpenWebUI password that was exposed!"
warn "After rotation, update GitHub secrets:"
echo "  gh secret set OPENWEBUI_EMAIL --body 'edenilson.adm@gmail.com'"
echo "  gh secret set OPENWEBUI_PASSWORD --body '<new-password>'"
