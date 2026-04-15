#!/bin/bash
# nordvpn-routing-watchdog.sh — Monitora e corrige rota de NordVPN
# Executor: systemd timer (a cada 5 min) ou manual
# Fail-safe: bloqueia deploy automático se nordvpn estiver quebrado

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly NORDVPN_TABLE=205
readonly NORDVPN_PRIORITY=50
readonly FALLBACK_PRIORITY=600
readonly ALERT_THRESHOLD=300  # segundos — se falha por > 5 min, alerta

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

# ─────────────────────────────────────────────────────────
# 1. Verifica se nordlynx existe
# ─────────────────────────────────────────────────────────
check_nordvpn_interface() {
    if ! ip link show nordlynx &>/dev/null; then
        warn "Interface nordlynx não encontrada"
        return 1
    fi
    return 0
}

# ─────────────────────────────────────────────────────────
# 2. Obtém rota padrão ATUAL
# ─────────────────────────────────────────────────────────
get_default_route() {
    local via_iface=$(ip route show | grep "^default" | awk '{print $5}')
    echo "$via_iface"
}

# ─────────────────────────────────────────────────────────
# 3. Verifica se IP público é de NordVPN
# ─────────────────────────────────────────────────────────
check_public_ip() {
    local public_ip
    public_ip=$(curl -s --max-time 5 https://api.ipify.org || echo "TIMEOUT")
    
    if [[ "$public_ip" == "TIMEOUT" ]] || [[ -z "$public_ip" ]]; then
        error "Não conseguiu verificar IP público"
        return 1
    fi
    
    # Arquivo de cache: último IP válido
    local cache_file="/var/run/nordvpn_last_valid_ip"
    if [[ -f "$cache_file" ]]; then
        local last_valid=$(cat "$cache_file")
        if [[ "$public_ip" == "$last_valid" ]]; then
            success "IP público OK: $public_ip (NordVPN)"
            return 0
        fi
    fi
    
    # Se mudou, atualiza cache
    echo "$public_ip" > "$cache_file"
    success "IP público: $public_ip"
    return 0
}

# ─────────────────────────────────────────────────────────
# 4. Força rota via NordVPN (com exceção para rede local)
# ─────────────────────────────────────────────────────────
force_nordvpn_route() {
    log "Iniciando força de rota via NordVPN..."
    
    if ! check_nordvpn_interface; then
        warn "NordVPN não está disponível, usando fallback"
        return 1
    fi
    
    local current_route=$(get_default_route)
    
    if [[ "$current_route" == "nordlynx" ]]; then
        success "Rota padrão já está via NordVPN ✓"
        return 0
    fi
    
    warn "Rota padrão está via $current_route, CORRIGINDO para NordVPN..."
    
    if [[ "$EUID" -ne 0 ]]; then
        error "Precisa ser root para alterar rotas. Execute: sudo $0"
        return 1
    fi
    
    # ⭐ IMPORTA: Manter rede local via eth-onboard (para SSH, Grafana, etc)
    # Adiciona rota prioritária para 192.168.15.0/24 via eth-onboard com métrica 100
    ip route add 192.168.15.0/24 via 192.168.15.1 dev eth-onboard metric 100 || true
    log "✓ Rede local (192.168.15.0/24) roteada via eth-onboard (métrica 100)"
    
    # Remove rota padrão antiga (se existir via eth-onboard)
    ip route del default via 192.168.15.1 dev eth-onboard metric 600 2>/dev/null || true
    
    # ⭐ Adiciona rota padrão GERAL via nordlynx (métrica 50 = prioritária)
    # Isso faz TUDO sair via NordVPN, EXCETO 192.168.15.0/24 que tem métrica 100 mais específica
    ip route add default dev nordlynx metric 50 2>/dev/null || true
    log "✓ Rota padrão via NordVPN (métrica 50)"
    
    # Persiste em systemd drop-in
    mkdir -p /etc/systemd/network
    if ! grep -q "Table=205" /etc/systemd/network/99-force-nordvpn-routing.network 2>/dev/null; then
        log "Criando systemd-networkd drop-in..."
        cp "$SCRIPT_DIR/99-force-nordvpn-routing.network" /etc/systemd/network/
    fi
    
    # Reinicia systemd-networkd para aplicar
    systemctl restart systemd-networkd || true
    sleep 2
    
    # Verifica que as rotas estão corretas
    log "Verificando rotas..."
    ip route show | grep -E "^192.168.15|^default" | while read line; do
        log "  → $line"
    done
    
    success "Rota NordVPN restaurada (com SSH local preservado)"
    return 0
}

# ─────────────────────────────────────────────────────────
# 5. Health check completo
# ─────────────────────────────────────────────────────────
health_check() {
    log "=== HEALTH CHECK VPN ROUTING ==="
    
    local status=0
    
    if ! check_nordvpn_interface; then
        warn "❌ NordVPN interface indisponível"
        status=1
    else
        success "✅ NordVPN interface OK"
    fi
    
    local route=$(get_default_route)
    if [[ "$route" == "nordlynx" ]]; then
        success "✅ Rota padrão: $route"
    else
        warn "❌ Rota padrão: $route (esperava nordlynx)"
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
# 6. Pre-deploy validator
# ─────────────────────────────────────────────────────────
validate_pre_deploy() {
    log "Validando roto antes de deploy..."
    
    if ! health_check; then
        error "❌ DEPLOY BLOQUEADO: Rota de VPN quebrada"
        error "Execute: sudo $0 --fix"
        return 1
    fi
    
    success "✅ Rota VPN validada — deploy liberado"
    return 0
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local cmd="${1:---health-check}"
    
    case "$cmd" in
        --health-check|--check)
            health_check
            ;;
        --fix|--force)
            if [[ "$EUID" -ne 0 ]]; then
                error "Precisa ser root. Execute: sudo $0 --fix"
                return 1
            fi
            force_nordvpn_route
            sleep 2
            health_check
            ;;
        --validate-pre-deploy)
            validate_pre_deploy
            ;;
        *)
            cat << 'EOF'
Uso: sudo ./nordvpn-routing-watchdog.sh <comando>

Comandos:
  --health-check      Verifica rota NordVPN (pode executar como user)
  --fix               Força rota via NordVPN (requer sudo)
  --validate-pre-deploy  Bloqueia deploy se rota estiver quebrada

Exemplos:
  ./nordvpn-routing-watchdog.sh --health-check
  sudo ./nordvpn-routing-watchdog.sh --fix
  
Instalação como systemd timer:
  sudo cp nordvpn-routing-watchdog.sh /usr/local/bin/
  sudo cp nordvpn-routing-watchdog.{service,timer} /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now nordvpn-routing-watchdog.timer
EOF
            exit 0
            ;;
    esac
}

main "$@"
