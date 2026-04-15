#!/bin/bash
# proxy-safe-mode.sh
# Protege rede local ANTES de ligar proxy manual
# 
# Problema: Proxy manual bloqueia tráfego para 192.168.15.0/24
# Solução: Configura firewall + routing para SEMPRE permitir rede local
#
# Uso: sudo bash proxy-safe-mode.sh --enable    # Execute ANTES de ligar proxy
#      sudo bash proxy-safe-mode.sh --disable   # Execute DEPOIS de desligar proxy

set -euo pipefail

readonly LOCAL_NET="192.168.15.0/24"
readonly LOCAL_GW="192.168.15.1"
readonly DNS_LOCAL="192.168.15.254"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
success() { echo "[$(date '+%H:%M:%S')] ✅ $*"; }
error() { echo "[$(date '+%H:%M:%S')] ❌ $*" >&2; }

# ─────────────────────────────────────────────────────────
# 1. IPTABLES: Permite TUDO de/para rede local
# ─────────────────────────────────────────────────────────
enable_local_firewall_bypass() {
    log "🔧 Configurando iptables para SEMPRE permitir rede local..."
    
    if [[ $EUID -ne 0 ]]; then
        error "Precisa ser root!"
        return 1
    fi
    
    # INPUT: aceita TUDO de 192.168.15.0/24
    iptables -I INPUT -s $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    # OUTPUT: permite TUDO para 192.168.15.0/24
    iptables -I OUTPUT -d $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    # FORWARD: permite tudo local
    iptables -I FORWARD -s $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    iptables -I FORWARD -d $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    success "✓ iptables configurado"
}

disable_local_firewall_bypass() {
    log "🔧 Removendo regras de bypass iptables..."
    
    if [[ $EUID -ne 0 ]]; then
        error "Precisa ser root!"
        return 1
    fi
    
    # Remove INPUT rules
    iptables -D INPUT -s $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    # Remove OUTPUT rules
    iptables -D OUTPUT -d $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    # Remove FORWARD rules
    iptables -D FORWARD -s $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    iptables -D FORWARD -d $LOCAL_NET -j ACCEPT -m comment --comment "PROXY_SAFE: Allow local network" 2>/dev/null || true
    
    success "✓ Regras removidas"
}

# ─────────────────────────────────────────────────────────
# 2. DNSMASQ: Resolve .local lokalmente MESMO com proxy
# ─────────────────────────────────────────────────────────
enable_local_dns() {
    log "🌐 Configurando dnsmasq para rede local..."
    
    # Se dnsmasq não está instalado, pula
    if ! command -v dnsmasq &>/dev/null; then
        log "⚠️  dnsmasq não instalado (pulando)"
        return 0
    fi
    
    # Cria config customizada
    sudo mkdir -p /etc/dnsmasq.d
    sudo tee /etc/dnsmasq.d/proxy-safe.conf > /dev/null << 'EOF'
# PROXY_SAFE: Resolve rede local mesmo com proxy ligado
address=/.homelab/192.168.15.2
address=/192.168.15.2.local/192.168.15.2
address=/eta.local/192.168.15.254
listen-address=127.0.0.1
EOF
    
    # Reinicia dnsmasq
    sudo systemctl restart dnsmasq || true
    success "✓ dnsmasq configurado"
}

disable_local_dns() {
    log "🌐 Removendo config dnsmasq..."
    sudo rm -f /etc/dnsmasq.d/proxy-safe.conf
    sudo systemctl restart dnsmasq || true
    success "✓ Config removida"
}

# ─────────────────────────────────────────────────────────
# 3. HOSTS: Fallback local se DNS falhar
# ─────────────────────────────────────────────────────────
enable_hosts_bypass() {
    log "📝 Adicionando entradas em /etc/hosts..."
    
    if sudo grep -q "PROXY_SAFE" /etc/hosts 2>/dev/null; then
        log "⚠️  Entradas ya presentes em /etc/hosts"
        return 0
    fi
    
    sudo tee -a /etc/hosts > /dev/null << 'EOF'

# PROXY_SAFE: Rede local — NUNCA ir para proxy
192.168.15.1 router.local
192.168.15.2 homelab homelab.local myClaude
192.168.15.254 eta.local
EOF
    
    success "✓ /etc/hosts atualizado"
}

disable_hosts_bypass() {
    log "📝 Removendo entradas de /etc/hosts..."
    sudo sed -i '/PROXY_SAFE/,/eta.local/d' /etc/hosts
    success "✓ Entradas removidas"
}

# ─────────────────────────────────────────────────────────
# 4. POLICY ROUTING: Força rede local SEMPRE via eth direta
# ─────────────────────────────────────────────────────────
enable_local_routing_policy() {
    log "🛣️  Configurando policy routing para rede local..."
    
    # Cria tabela 100 para tráfego local
    if ! grep -q "100" /etc/iproute2/rt_tables 2>/dev/null; then
        echo "100 local-bypass" | sudo tee -a /etc/iproute2/rt_tables > /dev/null
    fi
    
    # Adiciona règra: tráfego para 192.168.15.0/24 usa tabela 100
    sudo ip rule add to $LOCAL_NET table 100 priority 100 2>/dev/null || true
    
    # Adiciona rota em tabela 100
    sudo ip route add $LOCAL_NET via $LOCAL_GW table 100 2>/dev/null || true
    
    success "✓ Policy routing configurado"
}

disable_local_routing_policy() {
    log "🛣️  Removendo policy routing..."
    sudo ip rule del to $LOCAL_NET table 100 priority 100 2>/dev/null || true
    sudo ip route del $LOCAL_NET via $LOCAL_GW table 100 2>/dev/null || true
    success "✓ Policy routing removido"
}

# ─────────────────────────────────────────────────────────
# 5. PERSISTENT: Salva iptables e systemd service
# ─────────────────────────────────────────────────────────
save_iptables_rules() {
    log "💾 Salvando regras iptables..."
    sudo mkdir -p /etc/iptables
    sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
    success "✓ Regras salvas em /etc/iptables/rules.v4"
}

# ─────────────────────────────────────────────────────────
# 6. TESTE: Verifica se rede local funciona
# ─────────────────────────────────────────────────────────
test_local_connectivity() {
    log "🧪 Testando conectividade..."
    
    # Ping via IP
    if timeout 3 ping -c 1 192.168.15.2 &>/dev/null; then
        success "✓ Ping para 192.168.15.2 OK"
        return 0
    fi
    
    # Ping via hostname
    if timeout 3 ping -c 1 homelab 2>/dev/null | grep -q "bytes"; then
        success "✓ Ping para homelab OK"
        return 0
    fi
    
    # Tenta SSH
    if timeout 3 ssh -o ConnectTimeout=2 homelab@192.168.15.2 'echo OK' 2>/dev/null | grep -q OK; then
        success "✓ SSH para homelab OK"
        return 0
    fi
    
    error "✗ Nenhum teste passou (mas regras foram configuradas)"
    return 1
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local cmd="${1:---help}"
    
    case "$cmd" in
        --enable)
            log "🔒 Ativando PROXY_SAFE_MODE..."
            log "Execute ANTES de ligar proxy manual!"
            
            enable_local_firewall_bypass
            enable_hosts_bypass
            enable_local_routing_policy
            enable_local_dns
            save_iptables_rules
            
            log ""
            log "✅ PROXY_SAFE_MODE ATIVO"
            log "Agora você pode ligar o proxy sem perder rede local"
            log ""
            log "Para DESATIVAR: sudo bash $0 --disable"
            ;;
        
        --disable)
            log "🔓 Desativando PROXY_SAFE_MODE..."
            
            disable_local_firewall_bypass
            disable_hosts_bypass
            disable_local_routing_policy
            disable_local_dns
            
            log ""
            log "✅ PROXY_SAFE_MODE DESATIVADO"
            ;;
        
        --test)
            test_local_connectivity
            ;;
        
        --status)
            log "=== STATUS ==="
            echo ""
            log "Regras iptables com PROXY_SAFE:"
            sudo iptables -L -n 2>/dev/null | grep PROXY_SAFE || echo "  (nenhuma)"
            echo ""
            log "Entradas /etc/hosts:"
            sudo grep PROXY_SAFE /etc/hosts || echo "  (nenhuma)"
            echo ""
            log "Policy rules:"
            sudo ip rule show 2>/dev/null | grep "100" || echo "  (nenhuma)"
            ;;
        
        --help)
            cat << 'EOF'
🛡️  PROXY_SAFE_MODE — Protege rede local quando proxy está ligado

Uso: sudo bash proxy-safe-mode.sh <comando>

Comandos:
  --enable        Ativa proteção (execute ANTES de ligar proxy)
  --disable       Desativa proteção
  --test          Testa conectividade local
  --status        Mostra regras ativas

Exemplo de uso:
  1. sudo bash proxy-safe-mode.sh --enable
  2. Ligue o proxy manualmente no seu cliente VPN
  3. Rede local (192.168.15.0/24) continuará acessível
  4. sudo bash proxy-safe-mode.sh --disable    # quando terminar

O que faz:
  ✓ iptables INPUT/OUTPUT/FORWARD para 192.168.15.0/24
  ✓ /etc/hosts entradas cached para homelab
  ✓ dnsmasq local para .local domains
  ✓ Policy routing via tabela 100 (sempre local first)
  ✓ Persiste regras em /etc/iptables/rules.v4

Problemas solucionados:
  ✓ Proxy bloqueando SSH local
  ✓ Rede local desaparecendo quando proxy ativo
  ✓ DNS não resolvendo homelab
  ✓ Roteamento preferindo proxy ao invés de rede local

EOF
            ;;
        
        *)
            error "Comando desconhecido: $cmd"
            bash "$0" --help
            exit 1
            ;;
    esac
}

main "$@"
