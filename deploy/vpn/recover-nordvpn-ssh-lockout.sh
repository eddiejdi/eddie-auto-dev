#!/bin/bash
# recover-nordvpn-ssh-lockout.sh
# Recupera SSH local quando proxy/VPN bloqueia tráfego local
# 
# Uso: bash recover-nordvpn-ssh-lockout.sh [--reconnect]

set -euo pipefail

log() { echo "[$(date '+%H:%M:%S')] $*"; }
error() { echo "[$(date '+%H:%M:%S')] ❌ $*" >&2; }
success() { echo "[$(date '+%H:%M:%S')] ✅ $*"; }

LOCAL_NETWORK="192.168.15.0/24"
HOMELAB_IP="192.168.15.2"

detect_lan_iface() {
    local iface
    iface="$(ip route get "$HOMELAB_IP" 2>/dev/null | awk '/dev/ {for (i=1; i<=NF; i++) if ($i == "dev") {print $(i+1); exit}}')"
    echo "${iface:-enp0s31f6}"
}

# ─────────────────────────────────────────────────────────
# 1. Teste conectividade local
# ─────────────────────────────────────────────────────────
test_local_ssh() {
    log "Testando SSH local ($HOMELAB_IP)..."
    if timeout 3 ssh -o ConnectTimeout=3 homelab@$HOMELAB_IP 'echo OK' &>/dev/null; then
        success "SSH local OK ✓"
        return 0
    else
        error "SSH local bloqueado"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────
# 2. Restaura rota local (fallback imediato)
# ─────────────────────────────────────────────────────────
restore_local_route() {
    log "Restaurando rota local temporariamente..."
    
    if [[ $EUID -ne 0 ]]; then
        error "Precisa ser root. Execute: sudo bash $0"
        return 1
    fi

    local lan_iface
    lan_iface="$(detect_lan_iface)"
    
    # Reforça a rota direta da LAN sem depender de gateway legado.
    ip route replace "$LOCAL_NETWORK" dev "$lan_iface" scope link metric 10
    ip rule add to "$LOCAL_NETWORK" lookup main priority 100 2>/dev/null || true
    
    log "✓ Rota local restaurada em $lan_iface"
    sleep 1
    
    # Mostra rotas atuais
    log "Rotas ativas:"
    ip route show | grep -E "192.168.15|default" | sed 's/^/  → /'
    
    return 0
}

# ─────────────────────────────────────────────────────────
# 3. Verifica se NordVPN está conectado
# ─────────────────────────────────────────────────────────
check_nordvpn() {
    log "Verificando NordVPN..."
    
    if ssh homelab@$HOMELAB_IP 'systemctl is-active nordvpn-gui &>/dev/null && echo OK' 2>/dev/null | grep -q OK; then
        success "NordVPN serviço OK"
        return 0
    else
        error "NordVPN serviço desligado"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────
# 4. Reconecta NordVPN gradualmente
# ─────────────────────────────────────────────────────────
reconnect_nordvpn() {
    log "Reconectando NordVPN..."
    
    ssh homelab@$HOMELAB_IP bash << 'REMOTE'
set -euo pipefail

log() { echo "[$(date '+%H:%M:%S')] $*"; }
success() { echo "[$(date '+%H:%M:%S')] ✅ $*"; }

log "→ Conectando NordVPN..."
nordvpn connect || true
sleep 3

log "→ Verificando interface nordlynx..."
if ip link show nordlynx &>/dev/null; then
    success "✓ Interface nordlynx ativa"
else
    echo "Interface nordlynx não encontrada"
fi

REMOTE
    
    success "NordVPN reconectado"
    return 0
}

# ─────────────────────────────────────────────────────────
# 5. Aplica watchdog fix
# ─────────────────────────────────────────────────────────
apply_watchdog_fix() {
    log "Aplicando fix de roteamento inteligente..."
    
    ssh homelab@$HOMELAB_IP 'sudo /usr/local/bin/nordvpn-routing-watchdog.sh --fix' || {
        error "Watchdog fix falhou"
        return 1
    }
    
    success "Watchdog fix aplicado"
    return 0
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local mode="${1:---auto}"
    
    case "$mode" in
        --help)
            cat << 'EOF'
Uso: sudo bash recover-nordvpn-ssh-lockout.sh [modo]

Modos:
  --auto          Restaura SSH local + reconecta NordVPN gradualmente (padrão)
  --ssh-only      Apenas restaura SSH (sem mexer em NordVPN)
  --reconnect     Força reconexão de NordVPN com rotas corretas
  --check         Verifica status sem alterar nada

Exemplo:
  sudo bash recover-nordvpn-ssh-lockout.sh --auto
EOF
            exit 0
            ;;
        --check)
            log "=== STATUS ==="
            test_local_ssh && success "SSH local OK" || error "SSH local BLOQUEADO"
            check_nordvpn && success "NordVPN OK" || error "NordVPN DOWN"
            log "=== ROTAS ==="
            ip route show | grep -E "192.168|default"
            ;;
        --ssh-only)
            restore_local_route
            test_local_ssh
            ;;
        --reconnect)
            reconnect_nordvpn
            sleep 2
            apply_watchdog_fix
            ;;
        --auto)
            log "🔄 Recuperação automática..."
            
            # Passo 1: Restaura SSH
            if restore_local_route && test_local_ssh; then
                success "Passo 1: SSH restaurado ✓"
            else
                error "Falha ao restaurar SSH"
                exit 1
            fi
            
            # Passo 2: Reconecta NordVPN
            if reconnect_nordvpn; then
                success "Passo 2: NordVPN reconectado ✓"
            else
                error "Falha ao reconectar NordVPN (mas SSH funcionará)"
            fi
            
            # Passo 3: Aplica watchdog fix
            sleep 2
            if apply_watchdog_fix; then
                success "Passo 3: Watchdog fix aplicado ✓"
            else
                error "Falha no watchdog (mas SSH funcionará)"
            fi
            
            # Resultado final
            log ""
            log "=== STATUS FINAL ==="
            ip route show | grep -E "192.168.15|^default" | sed 's/^/  → /'
            echo ""
            test_local_ssh && success "SSH online" || error "SSH ainda offline"
            ;;
        *)
            error "Modo desconhecido: $mode"
            echo "Use: bash $0 --help"
            exit 1
            ;;
    esac
}

main "$@"
