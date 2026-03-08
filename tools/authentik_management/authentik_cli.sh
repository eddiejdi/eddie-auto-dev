#!/bin/bash
# Script para gerenciar usuários via CLI

AUTHENTIK_URL="${AUTHENTIK_URL:-https://auth.rpa4all.com}"
AUTHENTIK_TOKEN="${AUTHENTIK_TOKEN:-ak-homelab-authentik-api-2026}"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

function list_users() {
    echo "=== USUÁRIOS ==="
    curl -s -k -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        "$AUTHENTIK_URL/api/v3/core/users/?format=json" | jq '.results[] | {pk, username, email}'
}

function create_user() {
    local username=$1
    local email=$2
    local name=$3
    local password=$4
    
    echo "Criando usuário: $username"
    
    curl -s -k -X POST \
        -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"$username\",
            \"email\": \"$email\",
            \"name\": \"$name\",
            \"is_active\": true,
            \"password\": \"$password\"
        }" \
        "$AUTHENTIK_URL/api/v3/core/users/" | jq '.'
}

function list_groups() {
    echo "=== GRUPOS ==="
    curl -s -k -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        "$AUTHENTIK_URL/api/v3/core/groups/?format=json" | jq '.results[] | {pk, name}'
}

function create_group() {
    local name=$1
    
    echo "Criando grupo: $name"
    
    curl -s -k -X POST \
        -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$name\",
            \"name_en\": \"$name\"
        }" \
        "$AUTHENTIK_URL/api/v3/core/groups/" | jq '.'
}

function add_user_to_group() {
    local user_id=$1
    local group_id=$2
    
    echo "Adicionando usuário $user_id ao grupo $group_id"
    
    # Buscar grupos atuais do usuário
    local current_groups=$(curl -s -k -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        "$AUTHENTIK_URL/api/v3/core/users/$user_id/" | jq '.groups')
    
    # Adicionar novo grupo
    local new_groups=$(echo $current_groups | jq ". += [$group_id] | unique")
    
    # Atualizar usuário
    curl -s -k -X PATCH \
        -H "Authorization: Bearer $AUTHENTIK_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"groups\": $new_groups
        }" \
        "$AUTHENTIK_URL/api/v3/core/users/$user_id/" | jq '.'
}

case "$1" in
    list-users)
        list_users
        ;;
    create-user)
        create_user "$2" "$3" "$4" "$5"
        ;;
    list-groups)
        list_groups
        ;;
    create-group)
        create_group "$2"
        ;;
    add-to-group)
        add_user_to_group "$2" "$3"
        ;;
    *)
        echo "Uso: $0 {list-users|create-user|list-groups|create-group|add-to-group}"
        exit 1
        ;;
esac
