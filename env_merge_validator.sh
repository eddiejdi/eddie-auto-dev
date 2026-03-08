#!/bin/bash
# Validate and merge .env files across the project
# Usage: ./env_merge_validator.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONSOLIDATED="${SCRIPT_DIR}/.env.consolidated"
CURRENT_ENV="${SCRIPT_DIR}/.env"
BACKUP_DIR="${SCRIPT_DIR}/.env_backups"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Environment File Merge & Validator${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

if [ ! -f "$CONSOLIDATED" ]; then
    echo -e "${RED}✗ Error: .env.consolidated not found!${NC}"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# Function to validate required keys
validate_required_keys() {
    local env_file="$1"
    local required_keys=(
        "GOOGLE_AI_API_KEY"
        "HOME_ASSISTANT_URL"
        "HOME_ASSISTANT_TOKEN"
        "MAILU_DOMAIN"
        "MAILU_SECRET_KEY"
        "JIRA_URL"
        "JIRA_EMAIL"
        "JIRA_API_TOKEN"
        "KUCOIN_API_KEY"
        "KUCOIN_API_SECRET"
        "OLLAMA_HOST"
        "DATABASE_URL"
    )
    
    echo -e "\n${YELLOW}Validating required keys in ${env_file}...${NC}"
    
    local missing_count=0
    for key in "${required_keys[@]}"; do
        if grep -q "^${key}=" "$env_file" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $key"
        else
            echo -e "${RED}✗ MISSING:${NC} $key"
            ((missing_count++))
        fi
    done
    
    if [ $missing_count -eq 0 ]; then
        echo -e "\n${GREEN}✓ All required keys present!${NC}"
        return 0
    else
        echo -e "\n${RED}✗ Missing $missing_count required keys${NC}"
        return 1
    fi
}

# Function to detect duplicate keys
detect_duplicates() {
    local env_file="$1"
    echo -e "\n${YELLOW}Checking for duplicate keys in ${env_file}...${NC}"
    
    local dupes=$(grep -v '^#' "$env_file" | grep -v '^$' | cut -d'=' -f1 | sort | uniq -d)
    
    if [ -z "$dupes" ]; then
        echo -e "${GREEN}✓ No duplicate keys found${NC}"
    else
        echo -e "${RED}✗ Found duplicate keys:${NC}"
        echo "$dupes"
        return 1
    fi
}

main() {
    if validate_required_keys "$CONSOLIDATED" && detect_duplicates "$CONSOLIDATED"; then
        echo -e "\n${GREEN}✓ .env.consolidated is valid!${NC}"
    else
        echo -e "\n${RED}⚠ .env.consolidated issues${NC}"
        return 1
    fi
    
    if [ -f "$CURRENT_ENV" ]; then
        if validate_required_keys "$CURRENT_ENV" && detect_duplicates "$CURRENT_ENV"; then
            echo -e "\n${GREEN}✓ .env is valid!${NC}"
        else
            echo -e "\n${YELLOW}⚠ Current .env has issues, run 'cp .env.consolidated .env'${NC}"
        fi
    else
        echo -e "\n${YELLOW}Info: No .env file. Create from .env.consolidated${NC}"
    fi
    
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Summary:${NC}"
    echo -e "  Consolidated: .env.consolidated"
    echo -e "  Current: .env $([ -f "$CURRENT_ENV" ] && echo '(exists)' || echo '(missing)')"
    echo -e "  Backups: ${BACKUP_DIR}"
    echo -e "\n${BLUE}Merged components: Google Cloud • Home Assistant • Mailu • Jira • BTC Trading • Ollama • PostgreSQL${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

main
