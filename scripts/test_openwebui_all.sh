#!/usr/bin/env bash
# Test OpenWebUI credentials across all environments
# Usage: EMAIL='edenilson.adm@gmail.com' PASSWORD='Eddie@2026' ./test_openwebui_all.sh

set -euo pipefail

EMAIL="${EMAIL:-edenilson.adm@gmail.com}"
PASSWORD="${PASSWORD:-Eddie@2026}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok() { echo -e "${GREEN}[✓]${NC} $1"; }
log_err() { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${YELLOW}[i]${NC} $1"; }

test_openwebui() {
    local name="$1"
    local base_url="$2"
    
    echo
    log_info "Testing $name at $base_url"
    
    # Try signin
    local signin_resp
    signin_resp=$(curl -s -w "\n%{http_code}" -X POST "$base_url/api/v1/auths/signin" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" 2>/dev/null) || {
        log_err "$name: Connection failed"
        return 1
    }
    
    local http_code
    http_code=$(echo "$signin_resp" | tail -1)
    local body
    body=$(echo "$signin_resp" | head -n -1)
    
    if [[ "$http_code" == "200" ]]; then
        local token
        token=$(echo "$body" | jq -r '.token // empty' 2>/dev/null)
        if [[ -n "$token" ]]; then
            log_ok "$name: Signin successful"
            
            # Try to create API key
            local ak_resp
            ak_resp=$(curl -s -w "\n%{http_code}" -X POST "$base_url/api/v1/auths/api_key" \
                -H "Authorization: Bearer $token" \
                -H "Content-Type: application/json" \
                2>/dev/null) || {
                log_err "$name: API key creation - connection failed"
                return 1
            }
            
            local ak_code
            ak_code=$(echo "$ak_resp" | tail -1)
            local ak_body
            ak_body=$(echo "$ak_resp" | head -n -1)
            
            if [[ "$ak_code" == "200" ]] || [[ "$ak_code" == "201" ]]; then
                log_ok "$name: API key creation successful"
                return 0
            else
                log_err "$name: API key creation failed (HTTP $ak_code)"
                return 1
            fi
        else
            log_err "$name: No token in response"
            echo "Response: $body"
            return 1
        fi
    else
        log_err "$name: Signin failed (HTTP $http_code)"
        echo "Response: $body"
        return 1
    fi
}

echo "========================================"
echo "Testing OpenWebUI Credentials"
echo "========================================"
echo "Email: $EMAIL"
echo "Testing endpoints..."

results=()

# Test 1: Local (if running)
if [[ "${TEST_LOCAL:-false}" == "true" ]]; then
    if test_openwebui "Local (localhost:3000)" "http://localhost:3000"; then
        results+=("Local: OK")
    else
        results+=("Local: FAILED")
    fi
fi

# Test 2: Homelab (127.0.0.1 from homelab)
log_info "Testing Homelab (via SSH)..."
if ssh homelab@192.168.15.2 "curl -s -w '\n%{http_code}' -X POST 'http://127.0.0.1:3000/api/v1/auths/signin' -H 'Content-Type: application/json' -d '{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}' 2>/dev/null | grep -q '^200$'" 2>/dev/null; then
    log_ok "Homelab (127.0.0.1:3000): Signin successful"
    results+=("Homelab: OK")
else
    log_err "Homelab (127.0.0.1:3000): Signin failed"
    results+=("Homelab: FAILED")
fi

# Test 3: Docker container (open-webui on homelab)
log_info "Testing Docker container (open-webui on homelab)..."
if ssh homelab@192.168.15.2 "docker exec open-webui curl -s -w '\n%{http_code}' -X POST 'http://127.0.0.1:3000/api/v1/auths/signin' -H 'Content-Type: application/json' -d '{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}' 2>/dev/null | grep -q '^200$'" 2>/dev/null; then
    log_ok "Docker (open-webui): Signin successful"
    results+=("Docker (open-webui): OK")
else
    log_err "Docker (open-webui): Signin failed"
    results+=("Docker (open-webui): FAILED")
fi

echo
echo "========================================"
echo "Test Results:"
echo "========================================"
for r in "${results[@]}"; do
    echo "  $r"
done

# Check if all passed
if [[ ${#results[@]} -gt 0 ]] && echo "${results[@]}" | grep -q "OK"; then
    echo
    log_ok "At least one environment working correctly"
    exit 0
else
    echo
    log_err "No working environments found"
    exit 1
fi
