#!/bin/bash
# Homelab VPN Connection Script
# Connects to homelab via WireGuard over SSH tunnel + UDP-TCP relay

set -e

VPN_NAME="homelab-vpn"
RELAY_CLIENT_LOG="/tmp/relay-client.log"
RELAY_SCRIPT="$(dirname "$0")/udp_tcp_relay.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    local missing=()
    
    command -v wg >/dev/null 2>&1 || missing+=("wireguard-tools")
    command -v ssh >/dev/null 2>&1 || missing+=("openssh-client")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Install with: sudo apt install ${missing[*]}"
        exit 1
    fi
}

check_vpn_status() {
    if ip link show "$VPN_NAME" &>/dev/null; then
        return 0
    else
        return 1
    fi
}

disconnect_vpn() {
    log_info "Disconnecting VPN..."
    
    # Stop WireGuard
    if check_vpn_status; then
        sudo wg-quick down "$VPN_NAME" 2>/dev/null || sudo ip link delete "$VPN_NAME" 2>/dev/null || true
    fi
    
    # Stop relay client
    pkill -f 'udp_tcp_relay.py client' 2>/dev/null || true
    
    # Stop SSH tunnel
    pkill -f 'ssh.*51822:127.0.0.1:51821' 2>/dev/null || true
    
    # Stop cloudflared (fallback)
    pkill -f 'cloudflared access tcp.*vpn.rpa4all.com' 2>/dev/null || true
    
    log_info "VPN disconnected"
}

connect_vpn() {
    log_info "Connecting to Homelab VPN..."
    
    # Check if already connected
    if check_vpn_status; then
        log_warn "VPN already connected. Disconnecting first..."
        disconnect_vpn
        sleep 2
    fi
    
    # Check for conflicting interfaces
    if ip link show homelab-local &>/dev/null; then
        log_warn "Removing conflicting interface homelab-local..."
        sudo wg-quick down homelab-local 2>/dev/null || sudo ip link delete homelab-local 2>/dev/null || true
    fi
    
    # Start SSH tunnel with keepalive to prevent timeout
    log_info "Starting SSH tunnel..."
    ssh -f -N \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o TCPKeepAlive=yes \
        -o ExitOnForwardFailure=yes \
        -L 51822:127.0.0.1:51821 ssh.rpa4all.com || {
        log_warn "SSH tunnel failed, trying cloudflared..."
        cloudflared access tcp --hostname vpn.rpa4all.com --url localhost:51822 &
    }
    sleep 2
    
    # Verify tunnel is up
    if ! ss -tlnp 2>/dev/null | grep -q 51822; then
        log_error "Tunnel failed to start on port 51822"
        exit 1
    fi
    log_info "Tunnel established on port 51822"
    
    # Start relay client
    log_info "Starting UDP-TCP relay client..."
    if [ ! -f "$RELAY_SCRIPT" ]; then
        log_error "Relay script not found: $RELAY_SCRIPT"
        exit 1
    fi
    nohup python3 "$RELAY_SCRIPT" client --udp-listen 51823 --tcp-target 127.0.0.1:51822 > "$RELAY_CLIENT_LOG" 2>&1 &
    sleep 2
    
    # Verify relay is up
    if ! ss -ulnp 2>/dev/null | grep -q 51823; then
        log_error "Relay client failed to start on port 51823"
        log_info "Check logs: $RELAY_CLIENT_LOG"
        exit 1
    fi
    log_info "Relay client listening on UDP:51823"
    
    # Start WireGuard
    log_info "Starting WireGuard interface..."
    sudo wg-quick up "$VPN_NAME" || {
        log_error "Failed to start WireGuard. Check /etc/wireguard/$VPN_NAME.conf"
        disconnect_vpn
        exit 1
    }
    
    # Wait for handshake
    log_info "Waiting for WireGuard handshake..."
    sleep 3
    
    # Verify connection
    if ping -c 1 -W 3 10.66.66.1 &>/dev/null; then
        log_info "✅ VPN connected successfully!"
        log_info "Gateway: 10.66.66.1"
        log_info "Status: $(sudo wg show $VPN_NAME | grep -E 'handshake|transfer' | head -2)"
    else
        log_error "VPN interface is up but ping to gateway failed"
        log_info "Check logs: $RELAY_CLIENT_LOG"
        exit 1
    fi
}

status_vpn() {
    if check_vpn_status; then
        echo -e "${GREEN}VPN Status: Connected${NC}"
        echo ""
        sudo wg show "$VPN_NAME"
        echo ""
        echo "Routes:"
        ip route | grep -E "(10.66.66|192.168.15)" || echo "  No VPN routes found"
        echo ""
        echo "Testing connectivity..."
        if ping -c 1 -W 2 10.66.66.1 &>/dev/null; then
            echo -e "  Gateway (10.66.66.1): ${GREEN}✅ OK${NC}"
        else
            echo -e "  Gateway (10.66.66.1): ${RED}❌ FAIL${NC}"
        fi
        if ping -c 1 -W 2 192.168.15.2 &>/dev/null; then
            echo -e "  Internal (192.168.15.2): ${GREEN}✅ OK${NC}"
        else
            echo -e "  Internal (192.168.15.2): ${RED}❌ FAIL${NC}"
        fi
    else
        echo -e "${RED}VPN Status: Disconnected${NC}"
    fi
}

show_help() {
    cat <<EOF
Homelab VPN Connection Manager

Usage: $(basename "$0") [COMMAND]

Commands:
  connect     Connect to VPN (default)
  disconnect  Disconnect from VPN
  status      Show VPN status
  restart     Restart VPN connection
  watchdog    Run health-check loop (auto-reconnect)
  help        Show this help message

Examples:
  $(basename "$0")              # Connect to VPN
  $(basename "$0") disconnect   # Disconnect from VPN
  $(basename "$0") status       # Check VPN status
  $(basename "$0") watchdog     # Monitor and auto-reconnect

VPN Configuration: /etc/wireguard/$VPN_NAME.conf
Relay Log: $RELAY_CLIENT_LOG
EOF
}

watchdog_vpn() {
    local CHECK_INTERVAL="${WATCHDOG_INTERVAL:-30}"
    local FAIL_COUNT=0
    local MAX_FAILS=3
    log_info "Watchdog started (check every ${CHECK_INTERVAL}s, reconnect after ${MAX_FAILS} failures)"

    # Ensure VPN is connected on start
    if ! check_vpn_status || ! ping -c 1 -W 2 10.66.66.1 &>/dev/null; then
        log_warn "VPN not connected. Starting..."
        set +e
        disconnect_vpn 2>/dev/null
        sleep 2
        connect_vpn
        set -e
    fi

    while true; do
        sleep "$CHECK_INTERVAL"

        # Check 1: WireGuard interface exists
        if ! check_vpn_status; then
            log_warn "Watchdog: WireGuard interface down"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        # Check 2: SSH tunnel alive
        elif ! ss -tlnp 2>/dev/null | grep -q 51822; then
            log_warn "Watchdog: SSH tunnel down (port 51822)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        # Check 3: Relay alive
        elif ! ss -ulnp 2>/dev/null | grep -q 51823; then
            log_warn "Watchdog: Relay down (port 51823)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        # Check 4: Gateway reachable
        elif ! ping -c 1 -W 3 10.66.66.1 &>/dev/null; then
            log_warn "Watchdog: Gateway unreachable"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        else
            if [ "$FAIL_COUNT" -gt 0 ]; then
                log_info "Watchdog: Connection recovered"
            fi
            FAIL_COUNT=0
            continue
        fi

        if [ "$FAIL_COUNT" -ge "$MAX_FAILS" ]; then
            log_error "Watchdog: ${MAX_FAILS} consecutive failures — reconnecting..."
            FAIL_COUNT=0
            set +e
            disconnect_vpn
            sleep 3
            connect_vpn
            set -e
            log_info "Watchdog: Reconnection attempt complete"
        else
            log_warn "Watchdog: Failure $FAIL_COUNT/$MAX_FAILS"
        fi
    done
}

main() {
    check_dependencies
    
    case "${1:-connect}" in
        connect|start|up)
            connect_vpn
            ;;
        disconnect|stop|down)
            disconnect_vpn
            ;;
        status|show)
            status_vpn
            ;;
        restart|reconnect)
            disconnect_vpn
            sleep 2
            connect_vpn
            ;;
        watchdog|monitor)
            watchdog_vpn
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
