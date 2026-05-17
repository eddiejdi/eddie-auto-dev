#!/bin/bash
# iot-vpn-bypass.sh — Roteia dispositivos IoT (Tuya/smart home) diretamente
# via ISP, bypassando ProtonVPN. Resolve "rede anormal" de travas Tuya e
# dispositivos que rejeitam IPs de datacenter VPN.
#
# Problema: homelab-lan-gateway roteia TODA a LAN via protonvpn (tabela 205).
# Dispositivos Tuya detectam o IP ProtonVPN como VPN/datacenter e bloqueiam.
#
# Solução: policy routing — tabela 210 com default via ISP gateway.
# ip rule: from <IoT-IP> → tabela 210 (prioridade 150, antes da 205/protonvpn).
#
# Uso: sudo ./iot-vpn-bypass.sh --apply [--isp-gw 192.168.15.1]
#      sudo ./iot-vpn-bypass.sh --add-device 192.168.15.XXX
#      sudo ./iot-vpn-bypass.sh --remove-device 192.168.15.XXX
#      sudo ./iot-vpn-bypass.sh --list
#      sudo ./iot-vpn-bypass.sh --check
#
# Idempotente — pode ser executado várias vezes sem duplicar regras.

set -euo pipefail

readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly ISP_TABLE="${ISP_TABLE:-210}"
readonly ISP_TABLE_NAME="${ISP_TABLE_NAME:-isp-bypass}"
readonly ISP_RULE_PRIORITY="${ISP_RULE_PRIORITY:-150}"    # antes da 205 (protonvpn)
readonly RT_TABLES="/etc/iproute2/rt_tables"
readonly PERSIST_FILE="/etc/iot-vpn-bypass.conf"

log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
warn()    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

require_root() {
    if [[ "$EUID" -ne 0 ]]; then
        error "Execute como root: sudo $0 $*"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────
# Detecta o gateway ISP real (upstream do homelab, não o homelab em si)
# ─────────────────────────────────────────────────────────
detect_isp_gateway() {
    local gw

    # Pega o gateway padrão da interface LAN (ISP/modem/roteador)
    gw="$(ip route show dev "$LAN_INTERFACE" | awk '/^default/ {print $3; exit}')"

    if [[ -z "$gw" ]]; then
        # Fallback: tenta pegar o gateway da rota main (excluindo protonvpn)
        gw="$(ip route show table main | grep -v protonvpn | awk '/^default/ {print $3; exit}')"
    fi

    if [[ -z "$gw" ]]; then
        # Último recurso: assume .1 da rede LAN
        local lan_ip
        lan_ip="$(ip -4 addr show "$LAN_INTERFACE" | awk '/inet / {print $2}' | head -n1)"
        if [[ -n "$lan_ip" ]]; then
            gw="$(echo "$lan_ip" | sed 's|/.*||' | awk -F. '{print $1"."$2"."$3".1"}')"
            warn "Gateway não detectado automaticamente, assumindo $gw"
        fi
    fi

    echo "$gw"
}

# ─────────────────────────────────────────────────────────
# Configura a tabela de routing ISP bypass
# ─────────────────────────────────────────────────────────
setup_isp_table() {
    local isp_gw="$1"

    # Registra tabela em rt_tables
    if ! grep -qE "^${ISP_TABLE}\s" "$RT_TABLES" 2>/dev/null; then
        echo "${ISP_TABLE} ${ISP_TABLE_NAME}" >> "$RT_TABLES"
        log "Tabela ${ISP_TABLE} (${ISP_TABLE_NAME}) registrada em $RT_TABLES"
    fi

    # Rota default via ISP
    if ! ip route show table "$ISP_TABLE" 2>/dev/null | grep -q "^default"; then
        ip route add default via "$isp_gw" dev "$LAN_INTERFACE" table "$ISP_TABLE"
        log "Rota default → $isp_gw via $LAN_INTERFACE adicionada na tabela $ISP_TABLE"
    else
        log "Rota default na tabela $ISP_TABLE já existe"
    fi

    # Rota local da LAN na tabela ISP (para tráfego de retorno)
    local lan_cidr
    lan_cidr="$(ip -4 addr show "$LAN_INTERFACE" | awk '/inet / {print $2}' | head -n1 | sed 's|\.[0-9]*/|.0/|')"
    if [[ -n "$lan_cidr" ]]; then
        ip route replace "$lan_cidr" dev "$LAN_INTERFACE" scope link table "$ISP_TABLE" 2>/dev/null || true
    fi

    success "Tabela ISP bypass ($ISP_TABLE) configurada via $isp_gw"
}

# ─────────────────────────────────────────────────────────
# Adiciona um dispositivo IoT ao bypass
# ─────────────────────────────────────────────────────────
add_device() {
    local device_ip="$1"

    # Valida IP
    if ! [[ "$device_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        error "IP inválido: $device_ip"
        return 1
    fi

    # ip rule: from <device> → tabela ISP (antes do protonvpn/205)
    if ! ip rule show | grep -qE "from ${device_ip} lookup (${ISP_TABLE}|${ISP_TABLE_NAME})"; then
        ip rule add from "$device_ip" table "$ISP_TABLE" priority "$ISP_RULE_PRIORITY"
        log "ip rule adicionado: from $device_ip → tabela $ISP_TABLE (prioridade $ISP_RULE_PRIORITY)"
    else
        log "ip rule para $device_ip já existe"
    fi

    # MASQUERADE: tráfego do device sai com IP real da operadora
    if ! iptables -t nat -C POSTROUTING -s "$device_ip" -o "$LAN_INTERFACE" -j MASQUERADE \
        -m comment --comment "iot-bypass-${device_ip}" 2>/dev/null; then
        iptables -t nat -A POSTROUTING -s "$device_ip" -o "$LAN_INTERFACE" -j MASQUERADE \
            -m comment --comment "iot-bypass-${device_ip}"
        log "MASQUERADE adicionado: $device_ip → $LAN_INTERFACE"
    else
        log "MASQUERADE para $device_ip já existe"
    fi

    # FORWARD: permite o tráfego fluir
    if ! iptables -C FORWARD -s "$device_ip" -o "$LAN_INTERFACE" -j ACCEPT \
        -m comment --comment "iot-bypass-fwd-${device_ip}" 2>/dev/null; then
        iptables -I FORWARD 1 -s "$device_ip" -o "$LAN_INTERFACE" -j ACCEPT \
            -m comment --comment "iot-bypass-fwd-${device_ip}"
        log "FORWARD aceito: $device_ip → $LAN_INTERFACE"
    fi

    # Persiste no arquivo de config
    persist_device "$device_ip"

    success "Dispositivo $device_ip configurado para bypass VPN (ISP direto)"
}

# ─────────────────────────────────────────────────────────
# Remove um dispositivo do bypass
# ─────────────────────────────────────────────────────────
remove_device() {
    local device_ip="$1"

    ip rule del from "$device_ip" table "$ISP_TABLE" priority "$ISP_RULE_PRIORITY" 2>/dev/null && \
        log "ip rule removido: from $device_ip" || true

    while iptables -t nat -D POSTROUTING -s "$device_ip" -o "$LAN_INTERFACE" -j MASQUERADE \
        -m comment --comment "iot-bypass-${device_ip}" 2>/dev/null; do :; done
    log "MASQUERADE removido: $device_ip"

    while iptables -D FORWARD -s "$device_ip" -o "$LAN_INTERFACE" -j ACCEPT \
        -m comment --comment "iot-bypass-fwd-${device_ip}" 2>/dev/null; do :; done
    log "FORWARD removido: $device_ip"

    # Remove da persistência
    if [[ -f "$PERSIST_FILE" ]]; then
        sed -i "/^DEVICE=${device_ip}$/d" "$PERSIST_FILE"
    fi

    success "Dispositivo $device_ip removido do bypass"
}

# ─────────────────────────────────────────────────────────
# Persiste device no arquivo de config
# ─────────────────────────────────────────────────────────
persist_device() {
    local device_ip="$1"

    touch "$PERSIST_FILE"
    # Garante que ISP_GW esteja no arquivo
    if ! grep -q "^ISP_GW=" "$PERSIST_FILE" 2>/dev/null; then
        local gw
        gw="$(detect_isp_gateway)"
        echo "ISP_GW=${gw}" >> "$PERSIST_FILE"
    fi

    if ! grep -q "^DEVICE=${device_ip}$" "$PERSIST_FILE" 2>/dev/null; then
        echo "DEVICE=${device_ip}" >> "$PERSIST_FILE"
    fi
}

# ─────────────────────────────────────────────────────────
# Lista dispositivos e estado atual
# ─────────────────────────────────────────────────────────
list_devices() {
    log "=== DISPOSITIVOS IoT COM BYPASS VPN ==="
    echo ""

    if [[ -f "$PERSIST_FILE" ]]; then
        echo "Configuração persistida ($PERSIST_FILE):"
        cat "$PERSIST_FILE"
        echo ""
    else
        echo "(nenhum arquivo de config: $PERSIST_FILE)"
    fi

    echo "ip rules ativos (tabela $ISP_TABLE / $ISP_TABLE_NAME):"
    ip rule show | grep -E "lookup (${ISP_TABLE}|${ISP_TABLE_NAME})" || echo "  (nenhuma)"
    echo ""

    echo "MASQUERADE IoT ativos:"
    iptables -t nat -L POSTROUTING -v -n | grep "iot-bypass" || echo "  (nenhuma)"
    echo ""

    echo "Rotas na tabela $ISP_TABLE:"
    ip route show table "$ISP_TABLE" 2>/dev/null || echo "  (tabela vazia)"
}

# ─────────────────────────────────────────────────────────
# Health check — verifica se bypass está funcionando
# ─────────────────────────────────────────────────────────
check_bypass() {
    log "=== CHECK IoT VPN BYPASS ==="

    local isp_gw
    isp_gw="$(detect_isp_gateway)"

    if [[ -z "$isp_gw" ]]; then
        error "Não foi possível detectar o gateway ISP"
        return 1
    fi
    success "Gateway ISP detectado: $isp_gw"

    if grep -qE "^${ISP_TABLE}\s" "$RT_TABLES" 2>/dev/null; then
        success "Tabela $ISP_TABLE registrada"
    else
        warn "Tabela $ISP_TABLE NÃO registrada em $RT_TABLES"
    fi

    if ip route show table "$ISP_TABLE" 2>/dev/null | grep -q "^default"; then
        success "Rota default na tabela $ISP_TABLE OK"
    else
        warn "Rota default AUSENTE na tabela $ISP_TABLE"
    fi

    local devices=()
    if [[ -f "$PERSIST_FILE" ]]; then
        mapfile -t devices < <(grep "^DEVICE=" "$PERSIST_FILE" | cut -d= -f2)
    fi

    if [[ ${#devices[@]} -eq 0 ]]; then
        warn "Nenhum dispositivo IoT configurado ainda"
        log "Use: sudo $0 --add-device <IP-do-Tuya>"
        return 0
    fi

    for dev in "${devices[@]}"; do
        if ip rule show | grep -qE "from ${dev} lookup (${ISP_TABLE}|${ISP_TABLE_NAME})"; then
            success "ip rule OK: $dev → tabela $ISP_TABLE"
        else
            warn "ip rule AUSENTE para $dev"
        fi
    done
}

# ─────────────────────────────────────────────────────────
# Persiste regras no boot via systemd service
# ─────────────────────────────────────────────────────────
install_service() {
    local service_file="/etc/systemd/system/iot-vpn-bypass.service"

    cat > "$service_file" << EOF
[Unit]
Description=IoT VPN Bypass — roteia dispositivos Tuya/smart via ISP direto
After=network-online.target wg-quick@protonvpn.service
Wants=network-online.target
# Reinicia se protonvpn reiniciar (que limpa tabelas de routing)
PartOf=wg-quick@protonvpn.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/iot-vpn-bypass.sh --restore
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cp "$(realpath "$0")" /usr/local/bin/iot-vpn-bypass.sh
    chmod +x /usr/local/bin/iot-vpn-bypass.sh

    systemctl daemon-reload
    systemctl enable iot-vpn-bypass.service

    success "Serviço iot-vpn-bypass instalado e habilitado no boot"
    log "Dispositivos em $PERSIST_FILE serão restaurados automaticamente após reboot/protonvpn restart"
}

# ─────────────────────────────────────────────────────────
# Restaura do arquivo de config (usado pelo service)
# ─────────────────────────────────────────────────────────
restore_from_config() {
    if [[ ! -f "$PERSIST_FILE" ]]; then
        log "Nenhum arquivo de config ($PERSIST_FILE) — nada a restaurar"
        return 0
    fi

    log "Restaurando bypass IoT de $PERSIST_FILE..."

    local isp_gw
    isp_gw="$(grep "^ISP_GW=" "$PERSIST_FILE" | cut -d= -f2)"
    if [[ -z "$isp_gw" ]]; then
        isp_gw="$(detect_isp_gateway)"
    fi

    setup_isp_table "$isp_gw"

    while IFS= read -r line; do
        if [[ "$line" =~ ^DEVICE=(.+)$ ]]; then
            add_device "${BASH_REMATCH[1]}"
        fi
    done < "$PERSIST_FILE"

    save_iptables
    success "Bypass IoT restaurado"
}

# ─────────────────────────────────────────────────────────
# Salva iptables
# ─────────────────────────────────────────────────────────
save_iptables() {
    netfilter-persistent save 2>/dev/null || \
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
        warn "Não foi possível salvar iptables automaticamente (manual: iptables-save)"
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local cmd="${1:---help}"
    shift || true

    case "$cmd" in
        --apply)
            require_root
            local isp_gw="${1:-}"
            # Parse --isp-gw flag
            if [[ "$isp_gw" == "--isp-gw" ]]; then
                isp_gw="${2:-}"
            fi
            if [[ -z "$isp_gw" ]]; then
                isp_gw="$(detect_isp_gateway)"
            fi
            if [[ -z "$isp_gw" ]]; then
                error "Não foi possível detectar o gateway ISP. Use: sudo $0 --apply --isp-gw <IP>"
                exit 1
            fi
            log "Usando gateway ISP: $isp_gw"
            setup_isp_table "$isp_gw"
            save_iptables
            success "Tabela ISP bypass pronta. Adicione dispositivos com: sudo $0 --add-device <IP>"
            ;;

        --add-device)
            require_root
            local device_ip="${1:-}"
            if [[ -z "$device_ip" ]]; then
                error "Informe o IP: sudo $0 --add-device 192.168.15.XXX"
                exit 1
            fi
            # Garante que a tabela existe
            local isp_gw
            isp_gw="$(grep "^ISP_GW=" "$PERSIST_FILE" 2>/dev/null | cut -d= -f2 || true)"
            if [[ -z "$isp_gw" ]]; then
                isp_gw="$(detect_isp_gateway)"
            fi
            setup_isp_table "$isp_gw"
            add_device "$device_ip"
            save_iptables
            ;;

        --remove-device)
            require_root
            local device_ip="${1:-}"
            if [[ -z "$device_ip" ]]; then
                error "Informe o IP: sudo $0 --remove-device 192.168.15.XXX"
                exit 1
            fi
            remove_device "$device_ip"
            save_iptables
            ;;

        --list)
            list_devices
            ;;

        --check)
            check_bypass
            ;;

        --restore)
            require_root
            restore_from_config
            ;;

        --install-service)
            require_root
            install_service
            ;;

        --help|*)
            cat << 'EOF'
iot-vpn-bypass.sh — Roteia dispositivos IoT (Tuya/smart home) via ISP direto

Uso: sudo ./iot-vpn-bypass.sh <comando>

Comandos:
  --apply [--isp-gw <IP>]   Configura tabela ISP bypass (detecta gateway auto)
  --add-device <IP>          Adiciona dispositivo IoT ao bypass VPN
  --remove-device <IP>       Remove dispositivo do bypass
  --list                     Lista dispositivos e regras ativas
  --check                    Verifica se o bypass está funcionando
  --restore                  Restaura config do arquivo (usado pelo service)
  --install-service          Instala serviço systemd para persistir no boot

Fluxo rápido:
  1. Descubra o IP do Tuya no roteador/DHCP
  2. sudo ./iot-vpn-bypass.sh --apply
  3. sudo ./iot-vpn-bypass.sh --add-device 192.168.15.XXX
  4. sudo ./iot-vpn-bypass.sh --install-service  (persistir no boot)

Por que funciona:
  Cria tabela 210 (isp-bypass) com rota default via ISP gateway (eth-onboard).
  Adiciona "ip rule from <IoT-IP> lookup 210" com prioridade 150 — antes da
  tabela 205 (protonvpn). O kernel escolhe a tabela ISP primeiro para esse IP.
  MASQUERADE garante que o pacote sai com IP real da operadora.

EOF
            ;;
    esac
}

main "$@"
