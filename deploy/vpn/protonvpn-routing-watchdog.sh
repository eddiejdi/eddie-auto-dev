#!/bin/bash
# protonvpn-routing-watchdog.sh — Monitora e corrige rota de ProtonVPN
# Executor: systemd timer (a cada 5 min) ou manual
# Fail-safe: mantém o data-plane geral via protonvpn sem depender do roteador legado

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROTONVPN_IFACE="${PROTONVPN_IFACE:-protonvpn}"
readonly PROTONVPN_TABLE="${PROTONVPN_TABLE:-205}"
readonly PROTONVPN_FWMARK_FALLBACK="${PROTONVPN_FWMARK_FALLBACK:-0xca6c}"
readonly LAN_NETWORK="${LAN_NETWORK:-192.168.15.0/24}"
readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly LAN_GATEWAY_IP="${LAN_GATEWAY_IP:-192.168.15.2}"
readonly CHECK_CLIENT_IP="${CHECK_CLIENT_IP:-192.168.15.114}"
readonly PUBLIC_IP_CHECK_URL="${PUBLIC_IP_CHECK_URL:-https://api.ipify.org}"
readonly POLICY_RULE_PRIORITY="${POLICY_RULE_PRIORITY:-32764}"
readonly MAIN_SUPPRESS_PRIORITY="${MAIN_SUPPRESS_PRIORITY:-32765}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

get_protonvpn_fwmark() {
    local fwmark

    fwmark="$(wg show "$PROTONVPN_IFACE" fwmark 2>/dev/null | awk 'NF {print $1; exit}')"
    if [[ -z "$fwmark" || "$fwmark" == "off" ]]; then
        fwmark="$PROTONVPN_FWMARK_FALLBACK"
    fi

    echo "$fwmark"
}

# ─────────────────────────────────────────────────────────
# 1. Verifica se protonvpn existe
# ─────────────────────────────────────────────────────────
check_protonvpn_interface() {
    if ! ip link show "$PROTONVPN_IFACE" &>/dev/null; then
        warn "Interface $PROTONVPN_IFACE não encontrada"
        return 1
    fi
    return 0
}

# ─────────────────────────────────────────────────────────
# 2. Verifica se a tabela de policy routing continua indo para protonvpn
# ─────────────────────────────────────────────────────────
check_table_route() {
    if ! ip route show table "$PROTONVPN_TABLE" | grep -Eq "^default .*dev ${PROTONVPN_IFACE}( |$)|^default dev ${PROTONVPN_IFACE}( |$)"; then
        warn "Tabela $PROTONVPN_TABLE sem rota default via $PROTONVPN_IFACE"
        return 1
    fi
    return 0
}

check_policy_rules() {
    if ! ip rule show | grep -Eq "^${POLICY_RULE_PRIORITY}:.*lookup ${PROTONVPN_TABLE}( |$)"; then
        warn "Policy rule prioridade ${POLICY_RULE_PRIORITY} ausente para tabela ${PROTONVPN_TABLE}"
        return 1
    fi

    if ! ip rule show | grep -Eq "^${MAIN_SUPPRESS_PRIORITY}:.*lookup main suppress_prefixlength 0$"; then
        warn "Policy rule prioridade ${MAIN_SUPPRESS_PRIORITY} ausente para suppress_prefixlength 0"
        return 1
    fi

    return 0
}

# ─────────────────────────────────────────────────────────
# 3. Confirma que o caminho efetivo do homelab e da LAN aponta para protonvpn
# ─────────────────────────────────────────────────────────
check_effective_paths() {
    local homelab_path lan_path

    homelab_path="$(ip route get 1.1.1.1 from "$LAN_GATEWAY_IP" 2>/dev/null || true)"
    lan_path="$(ip route get 1.1.1.1 from "$CHECK_CLIENT_IP" iif "$LAN_INTERFACE" 2>/dev/null || true)"

    if [[ "$homelab_path" != *"dev $PROTONVPN_IFACE"* ]]; then
        warn "Tráfego do homelab não está saindo por $PROTONVPN_IFACE"
        return 1
    fi

    if [[ "$lan_path" != *"dev $PROTONVPN_IFACE"* ]]; then
        warn "Tráfego da LAN não está saindo por $PROTONVPN_IFACE"
        return 1
    fi

    return 0
}

# ─────────────────────────────────────────────────────────
# 4. Garante que a LAN segue diretamente conectada ao homelab
# ─────────────────────────────────────────────────────────
check_lan_route() {
    if ! ip route show "$LAN_NETWORK" | grep -q "$LAN_INTERFACE"; then
        warn "Rede local $LAN_NETWORK não está presente em $LAN_INTERFACE"
        return 1
    fi

    return 0
}

# ─────────────────────────────────────────────────────────
# 4b. Garante rotas LAN na tabela de policy routing (tabela 205)
#     Sem isso, respostas do Squid/DNS voltam pelo ProtonVPN em vez do LAN
# ─────────────────────────────────────────────────────────
check_table_lan_routes() {
    local missing=0
    if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${LAN_NETWORK} dev eth-onboard"; then
        warn "Rota LAN $LAN_NETWORK ausente na tabela $PROTONVPN_TABLE (eth-onboard)"
        missing=1
    fi
    if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${LAN_NETWORK} dev eth-wan"; then
        warn "Rota LAN $LAN_NETWORK ausente na tabela $PROTONVPN_TABLE (eth-wan)"
        missing=1
    fi
    return $missing
}

ensure_table_lan_routes() {
    if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${LAN_NETWORK} dev eth-onboard"; then
        ip route add table "$PROTONVPN_TABLE" "$LAN_NETWORK" dev eth-onboard scope link metric 100 2>/dev/null || \
        ip route replace table "$PROTONVPN_TABLE" "$LAN_NETWORK" dev eth-onboard scope link metric 100
        log "✓ Rota LAN $LAN_NETWORK → eth-onboard adicionada na tabela $PROTONVPN_TABLE"
    fi
    if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${LAN_NETWORK} dev eth-wan"; then
        ip route add table "$PROTONVPN_TABLE" "$LAN_NETWORK" dev eth-wan scope link metric 200 2>/dev/null || \
        ip route replace table "$PROTONVPN_TABLE" "$LAN_NETWORK" dev eth-wan scope link metric 200
        log "✓ Rota LAN $LAN_NETWORK → eth-wan adicionada na tabela $PROTONVPN_TABLE"
    fi
}

# ─────────────────────────────────────────────────────────
# 4c. Garante rotas Docker bridges na tabela 205
#     Sem isso, tráfego para bridges (172.25/16, 172.17/16) vai via ProtonVPN
# ─────────────────────────────────────────────────────────
check_table_docker_routes() {
    local missing=0
    local DOCKER_MONITORING_NET="172.25.0.0/16"
    local DOCKER_MONITORING_IFACE="br-d6ab85468718"
    local DOCKER_DEFAULT_NET="172.17.0.0/16"
    local DOCKER_DEFAULT_IFACE="docker0"

    if ip link show "$DOCKER_MONITORING_IFACE" &>/dev/null; then
        if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${DOCKER_MONITORING_NET} "; then
            warn "Rota Docker $DOCKER_MONITORING_NET ausente na tabela $PROTONVPN_TABLE"
            missing=1
        fi
    fi
    if ip link show "$DOCKER_DEFAULT_IFACE" &>/dev/null; then
        if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${DOCKER_DEFAULT_NET} "; then
            warn "Rota Docker $DOCKER_DEFAULT_NET ausente na tabela $PROTONVPN_TABLE"
            missing=1
        fi
    fi
    return $missing
}

ensure_table_docker_routes() {
    # homelab_monitoring bridge (Grafana, postgres)
    local DOCKER_MONITORING_NET="172.25.0.0/16"
    local DOCKER_MONITORING_IFACE="br-d6ab85468718"
    # docker0 default bridge
    local DOCKER_DEFAULT_NET="172.17.0.0/16"
    local DOCKER_DEFAULT_IFACE="docker0"

    if ip link show "$DOCKER_MONITORING_IFACE" &>/dev/null; then
        if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${DOCKER_MONITORING_NET} "; then
            ip route add table "$PROTONVPN_TABLE" "$DOCKER_MONITORING_NET" dev "$DOCKER_MONITORING_IFACE" scope link 2>/dev/null ||             ip route replace table "$PROTONVPN_TABLE" "$DOCKER_MONITORING_NET" dev "$DOCKER_MONITORING_IFACE" scope link
            log "✓ Rota Docker $DOCKER_MONITORING_NET → $DOCKER_MONITORING_IFACE adicionada na tabela $PROTONVPN_TABLE"
        fi
    fi

    if ip link show "$DOCKER_DEFAULT_IFACE" &>/dev/null; then
        if ! ip route show table "$PROTONVPN_TABLE" | grep -q "^${DOCKER_DEFAULT_NET} "; then
            ip route add table "$PROTONVPN_TABLE" "$DOCKER_DEFAULT_NET" dev "$DOCKER_DEFAULT_IFACE" scope link 2>/dev/null ||             ip route replace table "$PROTONVPN_TABLE" "$DOCKER_DEFAULT_NET" dev "$DOCKER_DEFAULT_IFACE" scope link
            log "✓ Rota Docker $DOCKER_DEFAULT_NET → $DOCKER_DEFAULT_IFACE adicionada na tabela $PROTONVPN_TABLE"
        fi
    fi
}

# ─────────────────────────────────────────────────────────
# 5. Verifica se IP público é de ProtonVPN
# ─────────────────────────────────────────────────────────
check_public_ip() {
    local public_ip
    public_ip="$(curl -4 -fsS --max-time 5 "$PUBLIC_IP_CHECK_URL" 2>/dev/null || echo "TIMEOUT")"

    if [[ "$public_ip" == "TIMEOUT" ]] || [[ -z "$public_ip" ]]; then
        error "Não conseguiu verificar IP público"
        return 1
    fi

    # Arquivo de cache: último IP válido
    local cache_dir="${PROTONVPN_CACHE_DIR:-/tmp}"
    local cache_file="$cache_dir/protonvpn_last_valid_ip"
    if [[ -f "$cache_file" ]]; then
        local last_valid=$(cat "$cache_file")
        if [[ "$public_ip" == "$last_valid" ]]; then
            success "IP público OK: $public_ip (ProtonVPN)"
            return 0
        fi
    fi

    # Se mudou, atualiza cache
    echo "$public_ip" > "$cache_file"
    success "IP público: $public_ip"
    return 0
}

# ─────────────────────────────────────────────────────────
# 6. Força rota policy via ProtonVPN sem tocar no underlay legado
# ─────────────────────────────────────────────────────────
force_protonvpn_route() {
    local fwmark

    log "Iniciando força de rota via ProtonVPN..."

    if ! check_protonvpn_interface; then
        warn "ProtonVPN não está disponível — tentando reconectar..."
        systemctl restart "wg-quick@${PROTONVPN_IFACE}" 2>/dev/null || true
        sleep 5
        if ! check_protonvpn_interface; then
            warn "Falha ao reconectar ProtonVPN"
            return 1
        fi
    fi

    if [[ "$EUID" -ne 0 ]]; then
        error "Precisa ser root para alterar rotas. Execute: sudo $0"
        return 1
    fi

    fwmark="$(get_protonvpn_fwmark)"

    ip route replace table "$PROTONVPN_TABLE" default dev "$PROTONVPN_IFACE"
    log "✓ Tabela $PROTONVPN_TABLE atualizada para $PROTONVPN_IFACE"

    ensure_table_lan_routes
    ensure_table_docker_routes

    while ip rule show | grep -Eq "^${POLICY_RULE_PRIORITY}:"; do
        ip rule del pref "$POLICY_RULE_PRIORITY" >/dev/null 2>&1 || break
    done
    ip rule add not fwmark "$fwmark" table "$PROTONVPN_TABLE" pref "$POLICY_RULE_PRIORITY"
    log "✓ Policy rule ${POLICY_RULE_PRIORITY} restaurada (not fwmark ${fwmark} -> tabela ${PROTONVPN_TABLE})"

    while ip rule show | grep -Eq "^${MAIN_SUPPRESS_PRIORITY}:"; do
        ip rule del pref "$MAIN_SUPPRESS_PRIORITY" >/dev/null 2>&1 || break
    done
    ip rule add lookup main suppress_prefixlength 0 pref "$MAIN_SUPPRESS_PRIORITY"
    log "✓ Policy rule ${MAIN_SUPPRESS_PRIORITY} restaurada (lookup main suppress_prefixlength 0)"

    ip route flush cache

    if [[ -f /etc/systemd/network/99-force-protonvpn-routing.network ]]; then
        rm -f /etc/systemd/network/99-force-protonvpn-routing.network
        log "✓ Drop-in conflitante do systemd-networkd removido"
    fi

    sleep 2

    if health_check; then
        success "Rota ProtonVPN restaurada"
        return 0
    fi

    error "Fix aplicado, mas a validação ainda falhou"
    return 1
}

# ─────────────────────────────────────────────────────────
# 7. Health check completo
# ─────────────────────────────────────────────────────────
health_check() {
    log "=== HEALTH CHECK VPN ROUTING ==="

    local status=0

    if ! check_protonvpn_interface; then
        warn "❌ ProtonVPN interface indisponível"
        status=1
    else
        success "✅ ProtonVPN interface OK"
    fi

    if check_table_route; then
        success "✅ Tabela $PROTONVPN_TABLE aponta para $PROTONVPN_IFACE"
    else
        status=1
    fi

    if check_policy_rules; then
        success "✅ Policy rules ${POLICY_RULE_PRIORITY}/${MAIN_SUPPRESS_PRIORITY} presentes"
    else
        status=1
    fi

    if check_effective_paths; then
        success "✅ Caminho efetivo do homelab/LAN usa $PROTONVPN_IFACE"
    else
        status=1
    fi

    if check_lan_route; then
        success "✅ LAN $LAN_NETWORK preservada em $LAN_INTERFACE"
    else
        status=1
    fi

    if check_table_lan_routes; then
        success "✅ Rotas LAN na tabela $PROTONVPN_TABLE presentes"
    else
        warn "⚠️  Rotas LAN ausentes na tabela $PROTONVPN_TABLE — corrigindo..."
        ensure_table_lan_routes
        ensure_table_docker_routes
        status=1
    fi

    if check_table_docker_routes; then
        success "✅ Rotas Docker bridges na tabela $PROTONVPN_TABLE presentes"
    else
        warn "⚠️  Rotas Docker bridges ausentes — corrigindo (container restart apaga rotas de iface down)..."
        ensure_table_docker_routes
        status=1
    fi

    if check_public_ip; then
        success "✅ IP público verificado"
    else
        warn "⚠️  Falha ao verificar IP público, mas o roteamento base foi mantido"
    fi

    return $status
}

# ─────────────────────────────────────────────────────────
# 8. Pre-deploy validator
# ─────────────────────────────────────────────────────────
validate_pre_deploy() {
    log "Validando rota antes de deploy..."

    if ! health_check; then
        error "❌ DEPLOY BLOQUEADO: Rota de VPN quebrada"
        error "Execute: sudo $0 --fix"
        return 1
    fi

    success "✅ Rota VPN validada — deploy liberado"
    return 0
}

# ─────────────────────────────────────────────────────────
# 9. Modo ensure
# ─────────────────────────────────────────────────────────
ensure_vpn() {
    if health_check; then
        return 0
    fi

    warn "Desvio detectado. Iniciando autocorreção..."
    force_protonvpn_route
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local cmd="${1:---ensure}"

    case "$cmd" in
        --health-check|--check)
            health_check
            ;;
        --fix|--force)
            if [[ "$EUID" -ne 0 ]]; then
                error "Precisa ser root. Execute: sudo $0 --fix"
                return 1
            fi
            force_protonvpn_route
            sleep 2
            health_check
            ;;
        --ensure)
            ensure_vpn
            ;;
        --validate-pre-deploy)
            validate_pre_deploy
            ;;
        *)
            cat << 'EOF'
Uso: sudo ./protonvpn-routing-watchdog.sh <comando>

Comandos:
  --ensure            Verifica e corrige automaticamente se houver desvio
  --health-check      Verifica rota ProtonVPN (pode executar como user)
  --fix               Força rota via ProtonVPN (requer sudo)
  --validate-pre-deploy  Bloqueia deploy se rota estiver quebrada

Exemplos:
  ./protonvpn-routing-watchdog.sh --ensure
  ./protonvpn-routing-watchdog.sh --health-check
  sudo ./protonvpn-routing-watchdog.sh --fix
EOF
            exit 0
            ;;
    esac
}

main "$@"
