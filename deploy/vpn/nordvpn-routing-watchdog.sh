#!/bin/bash
# nordvpn-routing-watchdog.sh — garante NordVPN em Panama com policy routing correta

set -euo pipefail

readonly TARGET_COUNTRY="${TARGET_COUNTRY:-Panama}"
readonly TARGET_TECHNOLOGY="${TARGET_TECHNOLOGY:-NORDLYNX}"
readonly NORDVPN_IFACE="${NORDVPN_IFACE:-nordlynx}"
readonly NORDVPN_TABLE="${NORDVPN_TABLE:-205}"
readonly LOCAL_NETWORK="${LOCAL_NETWORK:-192.168.15.0/24}"
readonly LOCAL_GATEWAY="${LOCAL_GATEWAY:-192.168.15.1}"
readonly LOCAL_INTERFACE="${LOCAL_INTERFACE:-eth-onboard}"
readonly CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-45}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $*" >&2; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: $*"; }

require_root() {
    if [[ "$EUID" -ne 0 ]]; then
        error "Precisa ser root. Execute com sudo."
        exit 1
    fi
}

require_nordvpn_cli() {
    if ! command -v nordvpn >/dev/null 2>&1; then
        error "CLI do NordVPN não encontrada"
        return 1
    fi
}

get_status_value() {
    local key="$1"
    nordvpn status 2>/dev/null | awk -F': ' -v key="$key" '$1 == key {print $2; exit}'
}

get_settings_value() {
    local key="$1"
    nordvpn settings 2>/dev/null | awk -F': ' -v key="$key" '$1 == key {print $2; exit}'
}

check_nordvpn_daemon() {
    if ! systemctl is-active --quiet nordvpnd; then
        warn "nordvpnd não está ativo"
        return 1
    fi
    return 0
}

check_interface() {
    if ! ip link show "$NORDVPN_IFACE" >/dev/null 2>&1; then
        warn "Interface $NORDVPN_IFACE não encontrada"
        return 1
    fi
    return 0
}

check_table_route() {
    if ! ip route show table "$NORDVPN_TABLE" | grep -Eq "^default .*dev ${NORDVPN_IFACE}( |$)|^default dev ${NORDVPN_IFACE}( |$)"; then
        warn "Tabela $NORDVPN_TABLE sem rota default via $NORDVPN_IFACE"
        return 1
    fi
    return 0
}

check_local_route() {
    if ip route show "$LOCAL_NETWORK" | grep -q "$LOCAL_INTERFACE"; then
        return 0
    fi

    warn "Rede local $LOCAL_NETWORK não está preservada via $LOCAL_INTERFACE"
    return 1
}

check_country() {
    local status country technology
    status="$(get_status_value "Status")"
    country="$(get_status_value "Country")"
    technology="$(get_status_value "Current technology")"

    if [[ "$status" != "Connected" ]]; then
        warn "NordVPN status atual: ${status:-desconhecido}"
        return 1
    fi

    if [[ "$country" != "$TARGET_COUNTRY" ]]; then
        warn "NordVPN conectada em ${country:-desconhecido}, esperado $TARGET_COUNTRY"
        return 1
    fi

    if [[ "$technology" != "$TARGET_TECHNOLOGY" ]]; then
        warn "Tecnologia atual ${technology:-desconhecida}, esperado $TARGET_TECHNOLOGY"
        return 1
    fi

    return 0
}

check_autoconnect() {
    local autoconnect technology
    autoconnect="$(get_settings_value "Auto-connect")"
    technology="$(get_settings_value "Technology")"

    if [[ "$autoconnect" != "enabled" ]]; then
        warn "Auto-connect está ${autoconnect:-desconhecido}"
        return 1
    fi

    if [[ "$technology" != "$TARGET_TECHNOLOGY" ]]; then
        warn "Tecnologia configurada ${technology:-desconhecida}, esperado $TARGET_TECHNOLOGY"
        return 1
    fi

    return 0
}

show_summary() {
    local status country server hostname technology
    status="$(get_status_value "Status")"
    country="$(get_status_value "Country")"
    server="$(get_status_value "Server")"
    hostname="$(get_status_value "Hostname")"
    technology="$(get_status_value "Current technology")"

    log "Resumo VPN:"
    log "  Status: ${status:-desconhecido}"
    log "  Country: ${country:-desconhecido}"
    log "  Server: ${server:-desconhecido}"
    log "  Hostname: ${hostname:-desconhecido}"
    log "  Technology: ${technology:-desconhecida}"
    log "  Table $NORDVPN_TABLE: $(ip route show table "$NORDVPN_TABLE" | tr '\n' '; ' | sed 's/; $//')"
}

health_check() {
    log "=== HEALTH CHECK NORDVPN ($TARGET_COUNTRY) ==="

    local status=0

    require_nordvpn_cli || return 1

    check_nordvpn_daemon || status=1
    check_interface || status=1
    check_table_route || status=1
    check_local_route || status=1
    check_country || status=1
    check_autoconnect || status=1

    show_summary

    if [[ "$status" -eq 0 ]]; then
        success "NordVPN saudável e fixada em $TARGET_COUNTRY"
    fi

    return "$status"
}

ensure_local_route() {
    ip route replace "$LOCAL_NETWORK" via "$LOCAL_GATEWAY" dev "$LOCAL_INTERFACE" metric 100
    success "Rede local preservada via $LOCAL_INTERFACE"
}

wait_for_panama() {
    local deadline now
    deadline=$((SECONDS + CONNECT_TIMEOUT))

    while true; do
        if check_interface && check_table_route && check_country; then
            return 0
        fi

        now=$SECONDS
        if (( now >= deadline )); then
            break
        fi

        sleep 3
    done

    return 1
}

force_panama() {
    require_root
    require_nordvpn_cli

    log "Aplicando correção para NordVPN em $TARGET_COUNTRY..."

    systemctl start nordvpnd || true
    ensure_local_route

    log "Fixando tecnologia em $TARGET_TECHNOLOGY e auto-connect em $TARGET_COUNTRY"
    nordvpn set technology "$TARGET_TECHNOLOGY"
    nordvpn set autoconnect on "$TARGET_COUNTRY"

    log "Reconectando NordVPN para $TARGET_COUNTRY"
    nordvpn disconnect >/dev/null 2>&1 || true
    timeout "$CONNECT_TIMEOUT" nordvpn connect "$TARGET_COUNTRY"

    if ! wait_for_panama; then
        error "NordVPN não estabilizou em $TARGET_COUNTRY dentro de ${CONNECT_TIMEOUT}s"
        show_summary
        return 1
    fi

    success "NordVPN reconectada em $TARGET_COUNTRY"
    health_check
}

ensure_vpn() {
    if health_check; then
        return 0
    fi

    warn "Desvio detectado. Iniciando autocorreção..."
    force_panama
}

main() {
    local cmd="${1:---ensure}"

    case "$cmd" in
        --health-check|--check)
            health_check
            ;;
        --fix|--force)
            force_panama
            ;;
        --ensure)
            ensure_vpn
            ;;
        *)
            cat <<EOF
Uso: sudo ./nordvpn-routing-watchdog.sh <comando>

Comandos:
  --ensure         Verifica e corrige automaticamente se sair de $TARGET_COUNTRY
  --health-check   Apenas valida status, país e rota da tabela $NORDVPN_TABLE
  --fix            Força reconexão NordVPN para $TARGET_COUNTRY
EOF
            exit 1
            ;;
    esac
}

main "$@"
