#!/bin/bash
# allow-ssh-through-proxy.sh
# Permite SSH local (192.168.15.0/24) mesmo com proxy/VPN manual ligado
#
# Problema: Quando proxy manual está ligado, SSH para rede local é bloqueado
# Solução: Excluir 192.168.15.0/24 do proxy

set -euo pipefail

log() { echo "[$(date '+%H:%M:%S')] $*"; }
error() { echo "[$(date '+%H:%M:%S')] ❌ $*" >&2; }
success() { echo "[$(date '+%H:%M:%S')] ✅ $*"; }

LOCAL_NETWORK="192.168.15.0/24"
HOMELAB_IP="192.168.15.2"

# ─────────────────────────────────────────────────────────
# 1. Detecta proxy ativo
# ─────────────────────────────────────────────────────────
detect_proxy() {
    log "Detectando proxy ativo..."
    
    # Procura por proxy em env vars
    if [[ -n "${HTTP_PROXY:-}" ]] || [[ -n "${HTTPS_PROXY:-}" ]]; then
        log "✓ Proxy encontrado em env vars"
        echo "${HTTP_PROXY:-${HTTPS_PROXY}}"
        return 0
    fi
    
    # Procura por proxy em /etc/environment
    if grep -q -i "proxy" /etc/environment 2>/dev/null; then
        log "✓ Proxy encontrado em /etc/environment"
        grep -i "proxy" /etc/environment | head -1 | cut -d'=' -f2-
        return 0
    fi
    
    # Procura por systemd proxy
    if [[ -f ~/.config/systemd/user.conf ]] && grep -q -i proxy ~/.config/systemd/user.conf; then
        log "✓ Proxy encontrado em systemd config"
        return 0
    fi
    
    log "Nenhum proxy env encontrado (verificar firewall/iptables)"
    return 1
}

# ─────────────────────────────────────────────────────────
# 2. Permite SSH via iptables (fallback se proxy está nulo)
# ─────────────────────────────────────────────────────────
allow_ssh_via_iptables() {
    log "Permitindo SSH local via iptables..."
    
    if [[ $EUID -ne 0 ]]; then
        error "Precisa ser root. Execute: sudo bash $0"
        return 1
    fi
    
    # INPUT: permite SSH da rede local mesmo com proxy
    sudo iptables -I INPUT -p tcp -s $LOCAL_NETWORK --dport 22 -j ACCEPT -m comment --comment "Allow local SSH" 2>/dev/null || true
    
    # OUTPUT: permite SSH para rede local
    sudo iptables -I OUTPUT -p tcp -d $LOCAL_NETWORK --dport 22 -j ACCEPT -m comment --comment "Allow local SSH" 2>/dev/null || true
    
    success "✓ SSH permitido em iptables"
    return 0
}

# ─────────────────────────────────────────────────────────
# 3. Cria bypass por networkmanager
# ─────────────────────────────────────────────────────────
configure_nm_bypass_proxy() {
    log "Configurando bypass de proxy em NetworkManager..."
    
    # Procura conexão WiFi/Ethernet ativa
    local conn_name=$(nmcli -t -f NAME connection show --active | head -1)
    
    if [[ -z "$conn_name" ]]; then
        error "Nenhuma conexão ativa"
        return 1
    fi
    
    log "Conexão ativa: $conn_name"
    
    # Adiciona 192.168.15.0/24 em ignore-hosts (bypass)
    nmcli connection modify "$conn_name" ipv4.ignore-auto-dns yes ipv4.dhcp-client-id "unique" 2>/dev/null || true
    
    # Se usar SOCKS/HTTP proxy, adicionar ignore-hosts
    log "Tentando configurar proxy bypass..."
    nmcli connection modify "$conn_name" 'ipv4.ignore-hosts' "$LOCAL_NETWORK" 2>/dev/null || true
    
    log "✓ NetworkManager configurado"
    return 0
}

# ─────────────────────────────────────────────────────────
# 4. Desliga proxy temporariamente para SSH
# ─────────────────────────────────────────────────────────
disable_proxy_for_ssh() {
    log "Salvando proxy config..."
    
    local proxy_backup="/tmp/proxy_backup_$$.env"
    
    # Salva env vars de proxy
    {
        echo "HTTP_PROXY=${HTTP_PROXY:-}"
        echo "HTTPS_PROXY=${HTTPS_PROXY:-}"
        echo "FTP_PROXY=${FTP_PROXY:-}"
        echo "NO_PROXY=${NO_PROXY:-}"
    } > "$proxy_backup"
    
    log "Backup salvo em: $proxy_backup"
    
    # Desliga proxy
    unset HTTP_PROXY HTTPS_PROXY FTP_PROXY NO_PROXY
    export NO_PROXY="*"
    
    log "✓ Proxy desligado temporariamente"
    echo "$proxy_backup"
    return 0
}

# ─────────────────────────────────────────────────────────
# 5. Testa SSH
# ─────────────────────────────────────────────────────────
test_ssh() {
    log "Testando SSH ($HOMELAB_IP)..."
    
    if timeout 5 ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no homelab@$HOMELAB_IP 'echo "SSH OK"' 2>&1; then
        success "SSH conectou! ✓"
        return 0
    else
        error "SSH ainda bloqueado"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local mode="${1:---auto}"
    
    case "$mode" in
        --help)
            cat << 'EOF'
Uso: sudo bash allow-ssh-through-proxy.sh [modo]

Modos:
  --auto           Tenta todas as   opções (padrão)
  --iptables       Configura firewall apenas
  --networkmanager Configura NetworkManager bypass
  --disable-proxy  Desliga proxy temporariamente
  --test           Testa SSH sem alterações

Exemplo:
  sudo bash allow-ssh-through-proxy.sh --auto
  
Depois de conectar:
  source /tmp/proxy_backup_*.env  # Restaura proxy
EOF
            exit 0
            ;;
        --test)
            test_ssh
            ;;
        --iptables)
            allow_ssh_via_iptables
            test_ssh
            ;;
        --networkmanager)
            configure_nm_bypass_proxy
            test_ssh
            ;;
        --disable-proxy)
            local backup=$(disable_proxy_for_ssh)
            log "Para restaurar proxy depois: source $backup"
            test_ssh && success "SSH agora funciona" || error "SSH ainda não funciona"
            ;;
        --auto)
            log "🔄 Permitindo SSH através de proxy..."
            
            # Tenta detectar proxy
            detect_proxy || log "Proxy não detectado (pode ser firewall)"
            
            # Tenta cada método
            log ""
            log "Método 1: iptables"
            allow_ssh_via_iptables
            sleep 1
            
            if test_ssh; then
                success "SSH funcionando!"
                exit 0
            fi
            
            log ""
            log "Método 2: NetworkManager bypass"
            configure_nm_bypass_proxy
            sleep 1
            nmcli connection reload
            sleep 1
            
            if test_ssh; then
                success "SSH funcionando!"
                exit 0
            fi
            
            log ""
            log "Método 3: Desligar proxy temporariamente"
            local backup=$(disable_proxy_for_ssh)
            sleep 1
            
            if test_ssh; then
                success "SSH funcionando!"
                log "Proxy pode ser restaurado com: source $backup"
                exit 0
            fi
            
            error "Todos os métodos falharam. Verifique:"
            log "  1. Se homelab está online: ping 192.168.15.2"
            log "  2. Se SSH está aberto: ssh -vv homelab@192.168.15.2"
            log "  3. Desabilite proxy manualmente em seu cliente VPN"
            exit 1
            ;;
        *)
            error "Modo desconhecido"
            bash "$0" --help
            exit 1
            ;;
    esac
}

main "$@"
