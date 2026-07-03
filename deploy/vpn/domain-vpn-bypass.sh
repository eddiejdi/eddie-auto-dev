#!/bin/bash
# domain-vpn-bypass.sh — Libera serviços bloqueados por VPN via ISP direto.
#
# Problema: ProtonVPN (tabela 205) roteia TODO o tráfego para fora.
# Serviços como Max/HBO Max detectam IP de datacenter e bloqueiam acesso.
#
# Solução: "ip rule to <dest-IP> lookup 210" com prioridade 145 — antes da
# tabela 205 (ProtonVPN, prio 32764) e antes do bypass por device (prio 150).
#
# Uso: sudo ./domain-vpn-bypass.sh --preset hbomax
#      sudo ./domain-vpn-bypass.sh --add-domain max.com
#      sudo ./domain-vpn-bypass.sh --refresh
#      sudo ./domain-vpn-bypass.sh --list
#      sudo ./domain-vpn-bypass.sh --install-timer
#
# Idempotente — pode ser executado várias vezes sem duplicar regras.

set -euo pipefail

readonly ISP_TABLE="${ISP_TABLE:-210}"
readonly ISP_TABLE_NAME="${ISP_TABLE_NAME:-isp-bypass}"
readonly DEST_RULE_PRIORITY="${DEST_RULE_PRIORITY:-145}"
readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly PERSIST_FILE="/etc/domain-vpn-bypass.conf"

log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: $*"; }
warn()    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $*" >&2; }

require_root() {
    [[ "$EUID" -eq 0 ]] || { error "Execute como root: sudo $0 $*"; exit 1; }
}

# ─────────────────────────────────────────────────────────
# Garante que a tabela ISP (210) está pronta com rota default
# (compartilhada com iot-vpn-bypass.sh — idempotente)
# ─────────────────────────────────────────────────────────
ensure_isp_table() {
    local isp_gw
    isp_gw="$(detect_isp_gateway)"

    if ! grep -qE "^${ISP_TABLE}\s" /etc/iproute2/rt_tables 2>/dev/null; then
        echo "${ISP_TABLE} ${ISP_TABLE_NAME}" >> /etc/iproute2/rt_tables
        log "Tabela ${ISP_TABLE} registrada"
    fi

    if ! ip route show table "$ISP_TABLE" 2>/dev/null | grep -q "^default"; then
        ip route add default via "$isp_gw" dev "$LAN_INTERFACE" table "$ISP_TABLE"
        local lan_cidr
        lan_cidr="$(ip -4 addr show "$LAN_INTERFACE" | awk '/inet / {print $2}' | head -n1 | sed 's|\.[0-9]*/|.0/|')"
        ip route replace "$lan_cidr" dev "$LAN_INTERFACE" scope link table "$ISP_TABLE" 2>/dev/null || true
        log "Rota default → $isp_gw via $LAN_INTERFACE adicionada na tabela $ISP_TABLE"
    fi
}

detect_isp_gateway() {
    local gw
    gw="$(ip route show dev "$LAN_INTERFACE" | awk '/^default/ {print $3; exit}')"
    if [[ -z "$gw" ]]; then
        gw="$(ip route show table main | grep -v protonvpn | awk '/^default/ {print $3; exit}')"
    fi
    if [[ -z "$gw" ]]; then
        error "Gateway ISP não detectado. Defina ISP_GW ou execute iot-vpn-bypass.sh --apply primeiro."
        exit 1
    fi
    echo "$gw"
}

# ─────────────────────────────────────────────────────────
# Adiciona/remove regra por destino
# ─────────────────────────────────────────────────────────
add_dest() {
    local dest_cidr="$1"

    if ip rule show | grep -qE "to ${dest_cidr//./\\.} lookup (${ISP_TABLE}|${ISP_TABLE_NAME})"; then
        log "Regra já existe: to $dest_cidr → tabela $ISP_TABLE"
        return 0
    fi

    ip rule add to "$dest_cidr" table "$ISP_TABLE" priority "$DEST_RULE_PRIORITY"
    log "Adicionado: to $dest_cidr → tabela $ISP_TABLE (prio $DEST_RULE_PRIORITY)"
}

remove_dest() {
    local dest_cidr="$1"
    ip rule del to "$dest_cidr" table "$ISP_TABLE" priority "$DEST_RULE_PRIORITY" 2>/dev/null \
        && log "Removido: to $dest_cidr" || true
}

# ─────────────────────────────────────────────────────────
# Resolução de domínio → IPs
# ─────────────────────────────────────────────────────────
resolve_ips() {
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

# ─────────────────────────────────────────────────────────
# Adiciona domínio (resolve + persiste + adiciona regras)
# ─────────────────────────────────────────────────────────
add_domain() {
    local domain="$1"
    log "Resolvendo $domain..."

    local ips
    ips="$(resolve_ips "$domain")"
    if [[ -z "$ips" ]]; then
        error "Nenhum IP resolvido para $domain"
        return 1
    fi

    local count=0
    while read -r ip; do
        add_dest "${ip}/32"
        touch "$PERSIST_FILE"
        grep -q "^DEST=${ip}/32$" "$PERSIST_FILE" 2>/dev/null || echo "DEST=${ip}/32" >> "$PERSIST_FILE"
        ((count++))
    done <<< "$ips"

    touch "$PERSIST_FILE"
    grep -q "^DOMAIN=${domain}$" "$PERSIST_FILE" 2>/dev/null || echo "DOMAIN=${domain}" >> "$PERSIST_FILE"

    success "$count IPs de ${domain} adicionados (bypass ISP direto)"
}

# ─────────────────────────────────────────────────────────
# Refresh: re-resolve todos os domínios (CDN muda IPs frequentemente)
# ─────────────────────────────────────────────────────────
do_refresh() {
    [[ -f "$PERSIST_FILE" ]] || { log "Nada a atualizar ($PERSIST_FILE não existe)"; return 0; }

    log "Removendo IPs antigos..."
    while IFS= read -r line; do
        [[ "$line" =~ ^DEST=(.+)$ ]] && remove_dest "${BASH_REMATCH[1]}" || true
    done < "$PERSIST_FILE"
    sed -i '/^DEST=/d' "$PERSIST_FILE"

    local domains=()
    mapfile -t domains < <(grep "^DOMAIN=" "$PERSIST_FILE" 2>/dev/null | cut -d= -f2 || true)

    log "Re-resolvendo ${#domains[@]} domínio(s)..."
    ensure_isp_table
    for domain in "${domains[@]}"; do
        add_domain "$domain" || warn "Falha ao resolver $domain (CDN indisponível?)"
    done

    ip route flush cache 2>/dev/null || true
    success "Refresh concluído (${#domains[@]} domínios)"
}

# ─────────────────────────────────────────────────────────
# Restaura do arquivo de config (usado pelo service no boot)
# ─────────────────────────────────────────────────────────
do_restore() {
    [[ -f "$PERSIST_FILE" ]] || { log "Nada a restaurar ($PERSIST_FILE não existe)"; return 0; }

    log "Restaurando regras de destino..."
    ensure_isp_table

    while IFS= read -r line; do
        [[ "$line" =~ ^DEST=(.+)$ ]] && add_dest "${BASH_REMATCH[1]}" || true
    done < "$PERSIST_FILE"

    ip route flush cache 2>/dev/null || true
    success "Regras restauradas"
}

# ─────────────────────────────────────────────────────────
# Presets
# ─────────────────────────────────────────────────────────
preset_hbomax() {
    local domains=(
        "max.com"
        "hbomax.com"
        "play.max.com"
        "api.max.com"
        "secure2.max.com"
        "img.max.com"
        "assets.max.com"
    )

    log "=== Liberando Max/HBO Max da VPN ==="
    ensure_isp_table

    for domain in "${domains[@]}"; do
        add_domain "$domain" || warn "Falha ao resolver $domain — continuando..."
    done

    ip route flush cache 2>/dev/null || true

    success "Max/HBO Max liberado — tráfego vai via ISP direto (sem VPN)"
    log ""
    log "Próximos passos recomendados:"
    log "  sudo $0 --install-timer   # refresh automático a cada 6h (CDN muda IPs)"
    log "  sudo $0 --install-service # persiste regras no boot"
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

    log "=== Liberando Amazon Prime Video da VPN ==="
    ensure_isp_table

    for domain in "${domains[@]}"; do
        add_domain "$domain" || warn "Falha ao resolver $domain — continuando..."
    done

    ip route flush cache 2>/dev/null || true

    success "Amazon Prime Video liberado — tráfego vai via ISP direto (sem VPN)"
    log ""
    log "Próximos passos recomendados:"
    log "  sudo $0 --install-timer   # refresh automático a cada 6h (CDN muda IPs)"
    log "  sudo $0 --install-service # persiste regras no boot"
}

# ─────────────────────────────────────────────────────────
# Instalação de timer systemd (refresh automático de IPs)
# ─────────────────────────────────────────────────────────
install_timer() {
    local script_dest="/usr/local/bin/domain-vpn-bypass.sh"

    if [[ "$(realpath "$0")" != "$script_dest" ]]; then
        cp "$(realpath "$0")" "$script_dest"
        chmod +x "$script_dest"
        log "Script copiado para $script_dest"
    fi

    cat > /etc/systemd/system/domain-vpn-refresh.service << EOF
[Unit]
Description=Refresh IPs de domínios no bypass VPN (CDN muda frequentemente)
After=network-online.target

[Service]
Type=oneshot
ExecStart=${script_dest} --refresh
StandardOutput=journal
StandardError=journal
EOF

    cat > /etc/systemd/system/domain-vpn-refresh.timer << EOF
[Unit]
Description=Atualiza IPs de bypass VPN a cada 6h

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    systemctl enable --now domain-vpn-refresh.timer

    success "Timer instalado — refresh automático a cada 6h"
    log "Status: systemctl status domain-vpn-refresh.timer"
}

# ─────────────────────────────────────────────────────────
# Instalação de service no boot
# ─────────────────────────────────────────────────────────
install_service() {
    local script_dest="/usr/local/bin/domain-vpn-bypass.sh"

    if [[ "$(realpath "$0")" != "$script_dest" ]]; then
        cp "$(realpath "$0")" "$script_dest"
        chmod +x "$script_dest"
        log "Script copiado para $script_dest"
    fi

    cat > /etc/systemd/system/domain-vpn-bypass.service << EOF
[Unit]
Description=Bypass VPN por destino — restaura regras de routing no boot
After=network-online.target wg-quick@protonvpn.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${script_dest} --restore
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now domain-vpn-bypass.service

    success "Serviço domain-vpn-bypass instalado e habilitado no boot"
}

# ─────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────
do_list() {
    log "=== BYPASS VPN POR DESTINO ==="
    echo ""

    echo "Domínios registrados ($PERSIST_FILE):"
    if [[ -f "$PERSIST_FILE" ]]; then
        grep "^DOMAIN=" "$PERSIST_FILE" 2>/dev/null | cut -d= -f2 || echo "  (nenhum)"
    else
        echo "  (sem arquivo de config)"
    fi
    echo ""

    echo "ip rules ativos — to <destino> lookup ${ISP_TABLE}:"
    ip rule show | grep -E "to .+ lookup (${ISP_TABLE}|${ISP_TABLE_NAME})" \
        | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n || echo "  (nenhuma)"
    echo ""

    echo "Total de IPs no bypass:"
    ip rule show | grep -cE "to .+ lookup (${ISP_TABLE}|${ISP_TABLE_NAME})" || echo "0"
}

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
main() {
    local cmd="${1:---help}"
    shift || true

    case "$cmd" in
        --preset)
            require_root
            local name="${1:-}"
            case "$name" in
                hbomax|max) preset_hbomax ;;
                amazonprime|prime) preset_amazonprime ;;
                *) error "Preset desconhecido: $name. Disponíveis: hbomax, amazonprime" ; exit 1 ;;
            esac
            ;;

        --add-domain)
            require_root
            local domain="${1:-}"
            [[ -n "$domain" ]] || { error "Informe o domínio: sudo $0 --add-domain max.com"; exit 1; }
            ensure_isp_table
            add_domain "$domain"
            ip route flush cache 2>/dev/null || true
            ;;

        --remove-domain)
            require_root
            local domain="${1:-}"
            [[ -n "$domain" ]] || { error "Informe o domínio: sudo $0 --remove-domain max.com"; exit 1; }
            local ips
            ips="$(resolve_ips "$domain" 2>/dev/null || true)"
            while read -r ip; do
                remove_dest "${ip}/32"
            done <<< "$ips"
            sed -i "/^DOMAIN=${domain//\./\\.}$/d" "$PERSIST_FILE" 2>/dev/null || true
            ip route flush cache 2>/dev/null || true
            success "Domínio $domain removido do bypass"
            ;;

        --refresh)
            require_root
            do_refresh
            ;;

        --restore)
            require_root
            do_restore
            ;;

        --list)
            do_list
            ;;

        --install-timer)
            require_root
            install_timer
            ;;

        --install-service)
            require_root
            install_service
            ;;

        --help|*)
            cat << 'EOF'
domain-vpn-bypass.sh — Libera serviços bloqueados por VPN via ISP direto

Uso: sudo ./domain-vpn-bypass.sh <comando> [args]

Comandos:
  --preset hbomax          Libera Max/HBO Max da VPN (resolve domínios + configura)
  --add-domain <domínio>   Adiciona bypass para um domínio específico
  --remove-domain <dom>    Remove bypass de um domínio
  --refresh                Re-resolve todos os domínios (CDN muda IPs)
  --restore                Restaura regras do arquivo de config (boot)
  --list                   Lista domínios e regras ativas
  --install-timer          Timer systemd: refresh automático a cada 6h
  --install-service        Serviço systemd: restaura regras no boot

Fluxo rápido — Max/HBO Max:
  sudo ./domain-vpn-bypass.sh --preset hbomax
  sudo ./domain-vpn-bypass.sh --install-timer    # mantém IPs CDN atualizados
  sudo ./domain-vpn-bypass.sh --install-service  # persiste no reboot

Fluxo rápido — Amazon Prime Video:
  sudo ./domain-vpn-bypass.sh --preset amazonprime
  sudo ./domain-vpn-bypass.sh --install-timer    # mantém IPs CDN atualizados
  sudo ./domain-vpn-bypass.sh --install-service  # persiste no reboot

Como funciona:
  Resolve os domínios do serviço para IPs e adiciona:
    "ip rule to <IP>/32 lookup 210 priority 145"
  O kernel consulta a tabela 210 (ISP direto, default via gateway local)
  antes da tabela 205 (ProtonVPN). O tráfego sai com IP real da operadora.
  IPs de CDN mudam — o --refresh-timer cuida de manter atualizado.

EOF
            ;;
    esac
}

main "$@"
