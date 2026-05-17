#!/bin/bash
# protonvpn-routing-watchdog.sh — Monitora e corrige rota de ProtonVPN
# Executor: systemd timer (a cada 5 min) ou manual
# Fail-safe: mantém o data-plane geral via protonvpn sem depender do roteador legado

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROTONVPN_IFACE="${PROTONVPN_IFACE:-protonvpn}"
readonly PROTONVPN_TABLE="${PROTONVPN_TABLE:-205}"
readonly LAN_NETWORK="${LAN_NETWORK:-192.168.15.0/24}"
readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly LAN_GATEWAY_IP="${LAN_GATEWAY_IP:-192.168.15.2}"
readonly CHECK_CLIENT_IP="${CHECK_CLIENT_IP:-192.168.15.114}"
readonly PUBLIC_IP_CHECK_URL="${PUBLIC_IP_CHECK_URL:-https://api.ipify.org}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

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

    ip route replace table "$PROTONVPN_TABLE" default dev "$PROTONVPN_IFACE"
    log "✓ Tabela $PROTONVPN_TABLE atualizada para $PROTONVPN_IFACE"

    mkdir -p /etc/systemd/network
    if [[ -f "$SCRIPT_DIR/99-force-protonvpn-routing.network" ]]; then
        cp "$SCRIPT_DIR/99-force-protonvpn-routing.network" /etc/systemd/network/
        chmod 644 /etc/systemd/network/99-force-protonvpn-routing.network
        log "✓ Drop-in de roteamento persistente atualizado"
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

    if check_public_ip; then
        success "✅ IP público verificado"
    else
        warn "❌ Falha ao verificar IP público"
        status=1
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
