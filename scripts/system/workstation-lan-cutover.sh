#!/bin/bash
# workstation-lan-cutover.sh — Promove Ethernet como primário com rollback temporizado

set -euo pipefail

readonly STATE_DIR="/var/lib/workstation-lan-cutover"
readonly ETH_CONN="${ETH_CONN:-Wired connection 1}"
readonly ETH_DEV="${ETH_DEV:-enp0s31f6}"
readonly WIFI_CONN="${WIFI_CONN:-TANK}"
readonly WIFI_DEV="${WIFI_DEV:-wlp2s0}"
readonly TARGET_GATEWAY="${TARGET_GATEWAY:-192.168.15.2}"
readonly TARGET_DNS="${TARGET_DNS:-192.168.15.2}"
readonly ROLLBACK_TIMEOUT="${ROLLBACK_TIMEOUT:-90}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

require_root() {
    if [[ "$EUID" -ne 0 ]]; then
        error "Precisa ser root. Execute com sudo."
        exit 1
    fi
}

nm_field() {
    local field="$1"
    local conn="$2"
    nmcli -g "$field" connection show "$conn" 2>/dev/null || true
}

dump_kv() {
    local key="$1"
    local value="${2-}"
    printf '%s=%q\n' "$key" "$value"
}

state_path() {
    local rollout_id="$1"
    echo "$STATE_DIR/$rollout_id.env"
}

rollback_unit() {
    local rollout_id="$1"
    echo "workstation-lan-cutover-$rollout_id"
}

save_state() {
    local rollout_id="$1"
    local file

    file="$(state_path "$rollout_id")"
    mkdir -p "$STATE_DIR"

    {
        dump_kv ETH_CONN "$ETH_CONN"
        dump_kv ETH_DEV "$ETH_DEV"
        dump_kv WIFI_CONN "$WIFI_CONN"
        dump_kv WIFI_DEV "$WIFI_DEV"
        dump_kv ETH_IPV4_METHOD "$(nm_field ipv4.method "$ETH_CONN")"
        dump_kv ETH_IPV4_ADDRESSES "$(nm_field ipv4.addresses "$ETH_CONN")"
        dump_kv ETH_IPV4_GATEWAY "$(nm_field ipv4.gateway "$ETH_CONN")"
        dump_kv ETH_IPV4_DNS "$(nm_field ipv4.dns "$ETH_CONN")"
        dump_kv ETH_IPV4_DNS_PRIORITY "$(nm_field ipv4.dns-priority "$ETH_CONN")"
        dump_kv ETH_IPV4_ROUTE_METRIC "$(nm_field ipv4.route-metric "$ETH_CONN")"
        dump_kv ETH_IPV4_NEVER_DEFAULT "$(nm_field ipv4.never-default "$ETH_CONN")"
        dump_kv ETH_IPV6_NEVER_DEFAULT "$(nm_field ipv6.never-default "$ETH_CONN")"
        dump_kv ETH_IPV6_ROUTE_METRIC "$(nm_field ipv6.route-metric "$ETH_CONN")"
        dump_kv ETH_AUTOCONNECT_PRIORITY "$(nm_field connection.autoconnect-priority "$ETH_CONN")"
        dump_kv WIFI_IPV4_METHOD "$(nm_field ipv4.method "$WIFI_CONN")"
        dump_kv WIFI_IPV4_DNS "$(nm_field ipv4.dns "$WIFI_CONN")"
        dump_kv WIFI_IPV4_DNS_PRIORITY "$(nm_field ipv4.dns-priority "$WIFI_CONN")"
        dump_kv WIFI_IPV4_ROUTE_METRIC "$(nm_field ipv4.route-metric "$WIFI_CONN")"
        dump_kv WIFI_IPV4_NEVER_DEFAULT "$(nm_field ipv4.never-default "$WIFI_CONN")"
        dump_kv WIFI_IPV6_NEVER_DEFAULT "$(nm_field ipv6.never-default "$WIFI_CONN")"
        dump_kv WIFI_IPV6_ROUTE_METRIC "$(nm_field ipv6.route-metric "$WIFI_CONN")"
        dump_kv WIFI_AUTOCONNECT_PRIORITY "$(nm_field connection.autoconnect-priority "$WIFI_CONN")"
        dump_kv WIFI_WAS_ACTIVE "$(nmcli -t -f NAME,DEVICE connection show --active | grep -Fx "$WIFI_CONN:$WIFI_DEV" >/dev/null && echo yes || echo no)"
    } > "$file"

    log "Checkpoint salvo em $file"
}

schedule_rollback() {
    local rollout_id="$1"
    local unit_name

    unit_name="$(rollback_unit "$rollout_id")"
    systemd-run --quiet --unit "$unit_name" --on-active="${ROLLBACK_TIMEOUT}s" \
        /bin/bash -lc "$(readlink -f "$0") --rollback-id '$rollout_id'"
    log "Rollback agendado para ${ROLLBACK_TIMEOUT}s (unit $unit_name)"
}

cancel_rollback() {
    local rollout_id="$1"
    local unit_name

    unit_name="$(rollback_unit "$rollout_id")"
    systemctl stop "${unit_name}.timer" "${unit_name}.service" 2>/dev/null || true
    systemctl reset-failed "${unit_name}.timer" "${unit_name}.service" 2>/dev/null || true
}

apply_cutover() {
    local eth_address

    eth_address="$(nm_field ipv4.addresses "$ETH_CONN")"
    if [[ -z "$eth_address" ]]; then
        error "Perfil Ethernet sem IPv4 configurado: $ETH_CONN"
        return 1
    fi

    nmcli connection modify "$ETH_CONN" \
        ipv4.method manual \
        ipv4.addresses "$eth_address" \
        ipv4.gateway "$TARGET_GATEWAY" \
        ipv4.dns "$TARGET_DNS" \
        ipv4.dns-priority -50 \
        ipv4.route-metric 100 \
        ipv4.never-default no \
        ipv6.never-default yes \
        ipv6.route-metric 100 \
        connection.autoconnect-priority 200

    nmcli connection modify "$WIFI_CONN" \
        ipv4.route-metric 600 \
        ipv4.dns-priority 600 \
        ipv4.never-default no \
        ipv6.never-default yes \
        ipv6.route-metric 600 \
        connection.autoconnect-priority 0

    nmcli connection up "$ETH_CONN" ifname "$ETH_DEV"
}

health_once() {
    timeout 4 ping -c 1 "$TARGET_GATEWAY" >/dev/null 2>&1 || return 1
    timeout 5 dig +time=2 +tries=1 @"$TARGET_DNS" google.com +short | grep -Eq '^[0-9]' || return 1
    timeout 5 dig +time=2 +tries=1 @"$TARGET_DNS" pi.hole +short | grep -Eq '^(192\.168\.15\.2|pi\.hole)' || return 1
    timeout 8 curl -4 --interface "$ETH_DEV" -fsS https://example.com >/dev/null || return 1
    ip route get 1.1.1.1 | grep -q "via $TARGET_GATEWAY dev $ETH_DEV" || return 1
}

validate_twice() {
    local attempt

    for attempt in 1 2; do
        if ! health_once; then
            error "Falha na validacao $attempt/2"
            return 1
        fi
        log "Validacao $attempt/2 OK"
        sleep 2
    done

    return 0
}

restore_connection() {
    local conn="$1"
    local prefix="$2"

    local ipv4_method ipv4_addresses ipv4_gateway ipv4_dns ipv4_dns_priority
    local ipv4_route_metric ipv4_never_default ipv6_never_default ipv6_route_metric autoconnect_priority

    ipv4_method="$(eval "printf '%s' \"\${${prefix}_IPV4_METHOD}\"")"
    ipv4_addresses="$(eval "printf '%s' \"\${${prefix}_IPV4_ADDRESSES-}\"")"
    ipv4_gateway="$(eval "printf '%s' \"\${${prefix}_IPV4_GATEWAY-}\"")"
    ipv4_dns="$(eval "printf '%s' \"\${${prefix}_IPV4_DNS-}\"")"
    ipv4_dns_priority="$(eval "printf '%s' \"\${${prefix}_IPV4_DNS_PRIORITY-}\"")"
    ipv4_route_metric="$(eval "printf '%s' \"\${${prefix}_IPV4_ROUTE_METRIC-}\"")"
    ipv4_never_default="$(eval "printf '%s' \"\${${prefix}_IPV4_NEVER_DEFAULT-}\"")"
    ipv6_never_default="$(eval "printf '%s' \"\${${prefix}_IPV6_NEVER_DEFAULT-}\"")"
    ipv6_route_metric="$(eval "printf '%s' \"\${${prefix}_IPV6_ROUTE_METRIC-}\"")"
    autoconnect_priority="$(eval "printf '%s' \"\${${prefix}_AUTOCONNECT_PRIORITY-}\"")"

    nmcli connection modify "$conn" \
        ipv4.method "$ipv4_method" \
        ipv4.addresses "$ipv4_addresses" \
        ipv4.gateway "$ipv4_gateway" \
        ipv4.dns "$ipv4_dns" \
        ipv4.dns-priority "$ipv4_dns_priority" \
        ipv4.route-metric "$ipv4_route_metric" \
        ipv4.never-default "$ipv4_never_default" \
        ipv6.never-default "$ipv6_never_default" \
        ipv6.route-metric "$ipv6_route_metric" \
        connection.autoconnect-priority "$autoconnect_priority"
}

rollback_id() {
    local rollout_id="$1"
    local file

    file="$(state_path "$rollout_id")"
    if [[ ! -f "$file" ]]; then
        error "Checkpoint nao encontrado: $file"
        return 1
    fi

    # shellcheck disable=SC1090
    source "$file"

    restore_connection "$ETH_CONN" ETH
    restore_connection "$WIFI_CONN" WIFI

    nmcli connection up "$ETH_CONN" ifname "$ETH_DEV" || true
    if [[ "${WIFI_WAS_ACTIVE:-no}" == "yes" ]]; then
        nmcli connection up "$WIFI_CONN" ifname "$WIFI_DEV" || true
    fi

    cancel_rollback "$rollout_id"
    success "Rollback aplicado para $rollout_id"
}

status() {
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP4.ROUTE dev show "$ETH_DEV"
    echo "---"
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP4.ROUTE dev show "$WIFI_DEV"
    echo "---"
    ip route
}

run_apply() {
    local rollout_id

    rollout_id="$(date +%Y%m%d%H%M%S)"
    save_state "$rollout_id"
    schedule_rollback "$rollout_id"
    apply_cutover

    if validate_twice; then
        cancel_rollback "$rollout_id"
        success "Cutover concluido com Ethernet primario via $TARGET_GATEWAY"
        return 0
    fi

    error "Cutover falhou, acionando rollback"
    rollback_id "$rollout_id"
}

main() {
    local cmd="${1:---apply}"

    case "$cmd" in
        --apply)
            require_root
            run_apply
            ;;
        --rollback-id)
            require_root
            rollback_id "${2:?faltou rollout id}"
            ;;
        --status)
            status
            ;;
        *)
            cat <<'EOF'
Uso: sudo ./workstation-lan-cutover.sh <comando>

Comandos:
  --apply          Promove Ethernet como primario com rollback temporizado
  --rollback-id    Restaura um checkpoint salvo
  --status         Mostra rotas e DNS atuais
EOF
            exit 1
            ;;
    esac
}

main "$@"
