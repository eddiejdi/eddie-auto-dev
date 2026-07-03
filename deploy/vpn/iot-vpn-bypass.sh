#!/bin/bash
# iot-vpn-bypass.sh — Roteia dispositivos IoT (Tuya/smart home) e serviços
# bloqueados por VPN diretamente via ISP, bypassando ProtonVPN.
#
# Problema: homelab-lan-gateway roteia TODA a LAN via protonvpn (tabela 205).
# Dispositivos Tuya e serviços como Max/HBO Max detectam IP de datacenter VPN.
#
# Solução: policy routing — tabela 210 com default via ISP gateway.
#   - Por dispositivo: ip rule from <IP-fonte> → tabela 210 (prioridade 150)
#   - Por destino:     ip rule to <IP-destino> → tabela 210 (prioridade 145)
#
# Uso: sudo ./iot-vpn-bypass.sh --apply [--isp-gw 192.168.15.1]
#      sudo ./iot-vpn-bypass.sh --add-device 192.168.15.XXX
#      sudo ./iot-vpn-bypass.sh --remove-device 192.168.15.XXX
#      sudo ./iot-vpn-bypass.sh --add-domain max.com
#      sudo ./iot-vpn-bypass.sh --preset hbomax
#      sudo ./iot-vpn-bypass.sh --refresh-domains
#      sudo ./iot-vpn-bypass.sh --list
#      sudo ./iot-vpn-bypass.sh --check
#
# Idempotente — pode ser executado várias vezes sem duplicar regras.

set -euo pipefail

readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly ISP_TABLE="${ISP_TABLE:-210}"
readonly ISP_TABLE_NAME="${ISP_TABLE_NAME:-isp-bypass}"
readonly ISP_RULE_PRIORITY="${ISP_RULE_PRIORITY:-150}"    # bypass por source (IoT)
readonly DEST_RULE_PRIORITY="${DEST_RULE_PRIORITY:-145}"  # bypass por destino (serviços)
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
# Bypass por DESTINO — serviços bloqueados por VPN (ex: Max/HBO Max)
# ip rule to <dest-cidr> → tabela 210 (prioridade 145, antes do source 150)
# ─────────────────────────────────────────────────────────
add_dest() {
    local dest_cidr="$1"

    if ! ip rule show | grep -qP "to ${dest_cidr//./\\.}(/32)? lookup (${ISP_TABLE}|${ISP_TABLE_NAME})"; then
        ip rule add to "$dest_cidr" table "$ISP_TABLE" priority "$DEST_RULE_PRIORITY"
        log "ip rule adicionado: to $dest_cidr → tabela $ISP_TABLE (prioridade $DEST_RULE_PRIORITY)"
    else
        log "ip rule para destino $dest_cidr já existe"
    fi
}

remove_dest() {
    local dest_cidr="$1"

    ip rule del to "$dest_cidr" table "$ISP_TABLE" priority "$DEST_RULE_PRIORITY" 2>/dev/null && \
        log "ip rule removido: to $dest_cidr" || true

    if [[ -f "$PERSIST_FILE" ]]; then
        sed -i "/^DEST=${dest_cidr//\//\\/}$/d" "$PERSIST_FILE"
    fi
}

resolve_domain_ips() {
    local domain="$1"
    local ips=""

    if command -v dig &>/dev/null; then
        ips="$(dig +short "$domain" A 2>/dev/null | grep -E '^[0-9]+\.' | sort -u)"
    fi
    if [[ -z "$ips" ]] && command -v host &>/dev/null; then
        ips="$(host -t A "$domain" 2>/dev/null | awk '/has address/ {print $4}' | sort -u)"
    fi
    if [[ -z "$ips" ]]; then
        ips="$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+\.' | sort -u)"
    fi
    echo "$ips"
}

add_dest_domain() {
    local domain="$1"
    log "Resolvendo $domain..."

    local isp_gw
    isp_gw="$(grep "^ISP_GW=" "$PERSIST_FILE" 2>/dev/null | cut -d= -f2 || true)"
    if [[ -z "$isp_gw" ]]; then
        isp_gw="$(detect_isp_gateway)"
    fi
    setup_isp_table "$isp_gw"

    local ips
    ips="$(resolve_domain_ips "$domain")"

    if [[ -z "$ips" ]]; then
        error "Nenhum IP resolvido para $domain"
        return 1
    fi

    local count=0
    while read -r ip; do
        add_dest "${ip}/32"
        touch "$PERSIST_FILE"
        if ! grep -q "^DEST=${ip}/32$" "$PERSIST_FILE" 2>/dev/null; then
            echo "DEST=${ip}/32" >> "$PERSIST_FILE"
        fi
        ((count++))
    done <<< "$ips"

    touch "$PERSIST_FILE"
    if ! grep -q "^DOMAIN=${domain}$" "$PERSIST_FILE" 2>/dev/null; then
        echo "DOMAIN=${domain}" >> "$PERSIST_FILE"
    fi

    success "$count IPs de $domain adicionados ao bypass ISP"
}

refresh_domains() {
    if [[ ! -f "$PERSIST_FILE" ]]; then
        log "Nenhum arquivo de config — nada a atualizar"
        return 0
    fi

    log "Limpando IPs antigos e re-resolvendo domínios..."

    while IFS= read -r line; do
        if [[ "$line" =~ ^DEST=(.+)$ ]]; then
            ip rule del to "${BASH_REMATCH[1]}" table "$ISP_TABLE" \
                priority "$DEST_RULE_PRIORITY" 2>/dev/null || true
        fi
    done < "$PERSIST_FILE"

    sed -i '/^DEST=/d' "$PERSIST_FILE"

    local domains=()
    mapfile -t domains < <(grep "^DOMAIN=" "$PERSIST_FILE" | cut -d= -f2)
    for domain in "${domains[@]}"; do
        add_dest_domain "$domain"
    done

    ip route flush cache 2>/dev/null || true
    save_iptables
    success "Domínios refreshed (${#domains[@]} domínios)"
}

# ─────────────────────────────────────────────────────────
# Presets de serviços conhecidos
# ─────────────────────────────────────────────────────────
preset_hbomax() {
    local domains=(
        "max.com"
        "hbomax.com"
        "play.max.com"
        "api.max.com"
        "secure2.max.com"
    )

    log "=== Configurando bypass ISP para Max/HBO Max ==="

    local isp_gw
    isp_gw="$(detect_isp_gateway)"
    setup_isp_table "$isp_gw"

    for domain in "${domains[@]}"; do
        add_dest_domain "$domain" || true
    done

    save_iptables
    success "Max/HBO Max liberado da VPN — tráfego vai via ISP direto"
    log "Para manter IPs atualizados: sudo $0 --refresh-domains"
    log "Para persistir no boot:      sudo $0 --install-service"
}

preset_amazonprime() {
    local domains=(
        "primevideo.com"
        "atv-ps.amazon.com"
        "aiv-cdn.net"
        "aiv-delivery.net"
        "d25xi40x97liuc.cloudfront.net"
        "fls-na.amazon.com"
        "api.amazon.com"
    )

    log "=== Configurando bypass ISP para Amazon Prime Video ==="

    local isp_gw
    isp_gw="$(detect_isp_gateway)"
    setup_isp_table "$isp_gw"

    for domain in "${domains[@]}"; do
        add_dest_domain "$domain" || warn "Falha ao resolver $domain — continuando..."
    done

    save_iptables
    success "Amazon Prime Video liberado da VPN — tráfego vai via ISP direto"
    log "Para manter IPs atualizados: sudo $0 --refresh-domains"
    log "Para persistir no boot:      sudo $0 --install-service"
}

install_refresh_timer() {
    local script_path="/usr/local/bin/iot-vpn-bypass.sh"
    local service_file="/etc/systemd/system/iot-vpn-domain-refresh.service"
    local timer_file="/etc/systemd/system/iot-vpn-domain-refresh.timer"

    cat > "$service_file" << EOF
[Unit]
Description=Refresh IPs de domínios no bypass VPN (CDN muda frequentemente)
After=network-online.target

[Service]
Type=oneshot
ExecStart=${script_path} --refresh-domains
StandardOutput=journal
StandardError=journal
EOF

    cat > "$timer_file" << EOF
[Unit]
Description=Atualiza IPs de domínios no bypass VPN a cada 6h

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    systemctl enable --now iot-vpn-domain-refresh.timer

    success "Timer de refresh instalado (a cada 6h)"
    log "Status: systemctl status iot-vpn-domain-refresh.timer"
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
    log "=== BYPASS VPN — DISPOSITIVOS E SERVIÇOS ==="
    echo ""

    if [[ -f "$PERSIST_FILE" ]]; then
        echo "Configuração persistida ($PERSIST_FILE):"
        cat "$PERSIST_FILE"
        echo ""
    else
        echo "(nenhum arquivo de config: $PERSIST_FILE)"
    fi

    echo "ip rules ativos — por DISPOSITIVO (from) tabela $ISP_TABLE:"
    ip rule show | grep -E "from .+ lookup (${ISP_TABLE}|${ISP_TABLE_NAME})" || echo "  (nenhuma)"
    echo ""

    echo "ip rules ativos — por DESTINO (to) tabela $ISP_TABLE:"
    ip rule show | grep -E "to .+ lookup (${ISP_TABLE}|${ISP_TABLE_NAME})" || echo "  (nenhuma)"
    echo ""

    echo "Domínios registrados:"
    if [[ -f "$PERSIST_FILE" ]]; then
        grep "^DOMAIN=" "$PERSIST_FILE" | cut -d= -f2 || echo "  (nenhum)"
    fi
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
        elif [[ "$line" =~ ^DEST=(.+)$ ]]; then
            add_dest "${BASH_REMATCH[1]}"
        fi
    done < "$PERSIST_FILE"

    save_iptables
    success "Bypass IoT/destinos restaurado"
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

        --add-domain)
            require_root
            local domain="${1:-}"
            if [[ -z "$domain" ]]; then
                error "Informe o domínio: sudo $0 --add-domain max.com"
                exit 1
            fi
            add_dest_domain "$domain"
            save_iptables
            ;;

        --remove-domain)
            require_root
            local domain="${1:-}"
            if [[ -z "$domain" ]]; then
                error "Informe o domínio: sudo $0 --remove-domain max.com"
                exit 1
            fi
            # Remove DEST entries associadas ao domínio (re-resolve para saber os IPs)
            local ips
            ips="$(resolve_domain_ips "$domain")"
            while read -r ip; do
                remove_dest "${ip}/32"
            done <<< "$ips"
            sed -i "/^DOMAIN=${domain//\./\\.}$/d" "$PERSIST_FILE" 2>/dev/null || true
            save_iptables
            ;;

        --add-dest)
            require_root
            local dest_cidr="${1:-}"
            if [[ -z "$dest_cidr" ]]; then
                error "Informe o CIDR: sudo $0 --add-dest 1.2.3.4/32"
                exit 1
            fi
            local isp_gw
            isp_gw="$(grep "^ISP_GW=" "$PERSIST_FILE" 2>/dev/null | cut -d= -f2 || true)"
            if [[ -z "$isp_gw" ]]; then
                isp_gw="$(detect_isp_gateway)"
            fi
            setup_isp_table "$isp_gw"
            add_dest "$dest_cidr"
            touch "$PERSIST_FILE"
            grep -q "^DEST=${dest_cidr}$" "$PERSIST_FILE" 2>/dev/null || echo "DEST=${dest_cidr}" >> "$PERSIST_FILE"
            save_iptables
            ;;

        --refresh-domains)
            require_root
            refresh_domains
            ;;

        --preset)
            require_root
            local preset_name="${1:-}"
            case "$preset_name" in
                hbomax|max) preset_hbomax ;;
                amazonprime|prime) preset_amazonprime ;;
                *) error "Preset desconhecido: $preset_name. Disponíveis: hbomax, amazonprime" ; exit 1 ;;
            esac
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

        --install-refresh-timer)
            require_root
            install_refresh_timer
            ;;

        --help|*)
            cat << 'EOF'
iot-vpn-bypass.sh — Roteia IoT e serviços bloqueados por VPN via ISP direto

Uso: sudo ./iot-vpn-bypass.sh <comando>

=== POR DISPOSITIVO (source) ===
  --apply [--isp-gw <IP>]    Configura tabela ISP bypass (detecta gateway auto)
  --add-device <IP>           Adiciona dispositivo IoT ao bypass VPN
  --remove-device <IP>        Remove dispositivo do bypass

=== POR SERVIÇO/DOMÍNIO (destino) ===
  --add-domain <domínio>      Resolve domínio e adiciona bypass por destino
  --remove-domain <domínio>   Remove domínio do bypass
  --add-dest <CIDR>           Adiciona CIDR específico ao bypass por destino
  --refresh-domains           Atualiza IPs de todos os domínios (CDN muda)
  --preset hbomax             Libera Max/HBO Max da VPN (atalho)
  --install-refresh-timer     Timer systemd: refresh automático a cada 6h

=== UTILITÁRIOS ===
  --list                      Lista dispositivos e regras ativas
  --check                     Verifica se o bypass está funcionando
  --restore                   Restaura config do arquivo (usado pelo service)
  --install-service           Instala serviço systemd para persistir no boot

Fluxo rápido — Max/HBO Max:
  sudo ./iot-vpn-bypass.sh --preset hbomax
  sudo ./iot-vpn-bypass.sh --install-refresh-timer   (mantém IPs CDN atualizados)
  sudo ./iot-vpn-bypass.sh --install-service         (persiste no boot)

Fluxo rápido — dispositivo IoT:
  sudo ./iot-vpn-bypass.sh --apply
  sudo ./iot-vpn-bypass.sh --add-device 192.168.15.XXX
  sudo ./iot-vpn-bypass.sh --install-service

Por que funciona:
  Tabela 210 (isp-bypass) tem rota default via ISP gateway.
  Por device: "ip rule from <IP> lookup 210" prio 150 — antes do ProtonVPN (205).
  Por destino: "ip rule to <IP> lookup 210" prio 145 — antes do source (150).
  MASQUERADE garante saída com IP real da operadora.

EOF
            ;;
    esac
}

main "$@"
