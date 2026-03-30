#!/bin/bash
# ddns-cloudflare-update.sh — Atualiza record DNS vpn.rpa4all.com no Cloudflare
# Roda no homelab (server-side) para manter o IP público atualizado
# Usado pelo timer systemd rpa4all-vpn-ddns-server.timer
set -euo pipefail

DOMAIN="vpn.rpa4all.com"
ZONE_ID="c9f221b503aff614b2d5fb4e8f365725"
RECORD_TYPE="A"
PROXIED="false"  # WireGuard precisa de DNS-only (sem proxy Cloudflare)
TTL=300
CACHE_FILE="/var/cache/rpa4all-ddns-server-ip"
LOG_TAG="rpa4all-ddns-server"

log() { echo "[${LOG_TAG}] $*"; logger -t "${LOG_TAG}" "$*" 2>/dev/null || true; }

# ── Obter CF API Token ──
get_cf_token() {
    # 1. Variável de ambiente
    if [ -n "${CF_API_TOKEN:-}" ]; then
        echo "${CF_API_TOKEN}"
        return
    fi
    # 2. Arquivo dedicado
    if [ -f /etc/cloudflare/ddns-token ]; then
        cat /etc/cloudflare/ddns-token
        return
    fi
    # 3. acme.sh account.conf (usado para DNS-01 certs)
    local acme_conf=""
    for path in /home/homelab/.acme.sh/account.conf /root/.acme.sh/account.conf; do
        if [ -f "${path}" ]; then
            acme_conf="${path}"
            break
        fi
    done
    if [ -n "${acme_conf}" ]; then
        local token
        # acme.sh armazena como SAVED_CF_Token ou CF_Token
        token=$(grep -oP "^SAVED_CF_Token='?\K[^']*" "${acme_conf}" 2>/dev/null || true)
        [ -z "${token}" ] && token=$(grep -oP "^CF_Token='?\K[^']*" "${acme_conf}" 2>/dev/null || true)
        if [ -n "${token}" ]; then
            echo "${token}"
            return
        fi
    fi
    log "ERRO: CF API Token não encontrado"
    exit 1
}

# ── Obter IP público atual ──
get_public_ip() {
    local ip=""
    for service in "https://ifconfig.me" "https://api.ipify.org" "https://icanhazip.com" "https://checkip.amazonaws.com"; do
        ip=$(curl -s --max-time 5 "${service}" 2>/dev/null | tr -d '[:space:]')
        if [[ "${ip}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "${ip}"
            return
        fi
    done
    log "ERRO: Falha ao obter IP público"
    exit 1
}

# ── Obter record ID existente ──
get_record_id() {
    local token="$1"
    local response
    response=$(curl -s --max-time 10 \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?type=${RECORD_TYPE}&name=${DOMAIN}")
    
    local success
    success=$(echo "${response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',''))" 2>/dev/null || echo "")
    if [ "${success}" != "True" ]; then
        log "ERRO: Falha ao consultar DNS records: ${response}"
        exit 1
    fi
    
    echo "${response}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
records = data.get('result', [])
if records:
    print(records[0]['id'])
else:
    print('')
" 2>/dev/null || echo ""
}

# ── Obter IP atual do record ──
get_record_ip() {
    local token="$1"
    local record_id="$2"
    if [ -z "${record_id}" ]; then
        echo ""
        return
    fi
    curl -s --max-time 10 \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${record_id}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('content',''))" 2>/dev/null || echo ""
}

# ── Criar record ──
create_record() {
    local token="$1"
    local ip="$2"
    local response
    response=$(curl -s --max-time 10 -X POST \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"type\":\"${RECORD_TYPE}\",\"name\":\"${DOMAIN}\",\"content\":\"${ip}\",\"ttl\":${TTL},\"proxied\":${PROXIED}}" \
        "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records")
    
    local success
    success=$(echo "${response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',''))" 2>/dev/null || echo "")
    if [ "${success}" = "True" ]; then
        log "Record criado: ${DOMAIN} → ${ip} (DNS-only, TTL=${TTL})"
    else
        log "ERRO ao criar record: ${response}"
        exit 1
    fi
}

# ── Atualizar record ──
update_record() {
    local token="$1"
    local record_id="$2"
    local ip="$3"
    local response
    response=$(curl -s --max-time 10 -X PATCH \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" \
        -d "{\"content\":\"${ip}\",\"ttl\":${TTL},\"proxied\":${PROXIED}}" \
        "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${record_id}")
    
    local success
    success=$(echo "${response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',''))" 2>/dev/null || echo "")
    if [ "${success}" = "True" ]; then
        log "Record atualizado: ${DOMAIN} → ${ip} (DNS-only, TTL=${TTL})"
    else
        log "ERRO ao atualizar record: ${response}"
        exit 1
    fi
}

# ═══ MAIN ═══

CF_TOKEN=$(get_cf_token)
PUBLIC_IP=$(get_public_ip)

# Verificar cache
CACHED_IP=""
[ -f "${CACHE_FILE}" ] && CACHED_IP=$(cat "${CACHE_FILE}" 2>/dev/null || true)

if [ "${PUBLIC_IP}" = "${CACHED_IP}" ]; then
    log "IP inalterado: ${PUBLIC_IP}"
    exit 0
fi

log "IP público: ${PUBLIC_IP} (anterior: ${CACHED_IP:-desconhecido})"

RECORD_ID=$(get_record_id "${CF_TOKEN}")

if [ -z "${RECORD_ID}" ]; then
    log "Record ${DOMAIN} não existe, criando..."
    create_record "${CF_TOKEN}" "${PUBLIC_IP}"
else
    CURRENT_IP=$(get_record_ip "${CF_TOKEN}" "${RECORD_ID}")
    if [ "${CURRENT_IP}" = "${PUBLIC_IP}" ]; then
        log "Record já atualizado: ${PUBLIC_IP}"
        echo "${PUBLIC_IP}" > "${CACHE_FILE}"
        exit 0
    fi
    log "Atualizando ${DOMAIN}: ${CURRENT_IP} → ${PUBLIC_IP}"
    update_record "${CF_TOKEN}" "${RECORD_ID}" "${PUBLIC_IP}"
fi

echo "${PUBLIC_IP}" > "${CACHE_FILE}"
log "Concluído."
