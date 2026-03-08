#!/bin/bash
# =============================================================================
# Shared System Optimizer - Manutenção e Performance
# Machine: Intel i5-6300U / 16GB RAM / NVMe / LMDE (Debian 13)
# Created: 2026-03-01
# Usage: sudo bash tools/optimize_system.sh [--clean|--tune|--status|--full]
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# ---- STATUS ----
show_status() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  SHARED SYSTEM STATUS  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}\n"

    # Load
    local load=$(awk '{print $1}' /proc/loadavg)
    local cpus=$(nproc)
    local load_ratio=$(echo "$load $cpus" | awk '{printf "%.1f", $1/$2}')
    if (( $(echo "$load_ratio > 2" | bc -l) )); then
        err "Load: ${load} (${load_ratio}x CPUs) — SOBRECARREGADO"
    elif (( $(echo "$load_ratio > 1" | bc -l) )); then
        warn "Load: ${load} (${load_ratio}x CPUs) — acima do ideal"
    else
        log "Load: ${load} (${load_ratio}x CPUs) — OK"
    fi

    # RAM
    local ram_used_pct=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    local ram_free=$(free -h | awk '/^Mem:/ {print $4}')
    if (( ram_used_pct > 90 )); then
        err "RAM: ${ram_used_pct}% usado (livre: ${ram_free}) — CRÍTICO"
    elif (( ram_used_pct > 75 )); then
        warn "RAM: ${ram_used_pct}% usado (livre: ${ram_free})"
    else
        log "RAM: ${ram_used_pct}% usado (livre: ${ram_free})"
    fi

    # Swap
    local swap_total=$(free | awk '/^Swap:/ {print $2}')
    if (( swap_total > 0 )); then
        local swap_used_pct=$(free | awk '/^Swap:/ {printf "%.0f", $3/$2*100}')
        if (( swap_used_pct > 80 )); then
            err "Swap: ${swap_used_pct}% usado — THRASHING PROVÁVEL"
        elif (( swap_used_pct > 50 )); then
            warn "Swap: ${swap_used_pct}% usado"
        else
            log "Swap: ${swap_used_pct}% usado"
        fi
    fi

    # Disco
    local disk_pct=$(df / | awk 'NR==2 {gsub(/%/,""); print $5}')
    local disk_free=$(df -h / | awk 'NR==2 {print $4}')
    if (( disk_pct > 90 )); then
        err "Disco: ${disk_pct}% (livre: ${disk_free}) — ATENÇÃO"
    elif (( disk_pct > 80 )); then
        warn "Disco: ${disk_pct}% (livre: ${disk_free})"
    else
        log "Disco: ${disk_pct}% (livre: ${disk_free})"
    fi

    # Firefox tabs
    local ff_tabs=$(ps aux 2>/dev/null | grep -c 'firefox.*tab' || echo 0)
    if (( ff_tabs > 20 )); then
        err "Firefox: ${ff_tabs} abas — REDUZIR para < 15"
    elif (( ff_tabs > 10 )); then
        warn "Firefox: ${ff_tabs} abas"
    else
        log "Firefox: ${ff_tabs} abas"
    fi

    # kswapd
    local kswapd_cpu=$(ps aux 2>/dev/null | awk '/\[kswapd0\]/ {print $3}')
    if [[ -n "$kswapd_cpu" ]] && (( $(echo "$kswapd_cpu > 2" | bc -l 2>/dev/null || echo 0) )); then
        err "kswapd0: ${kswapd_cpu}% CPU — swap thrashing ativo"
    else
        log "kswapd0: OK"
    fi

    # Top 5 por RAM
    echo -e "\n${CYAN}Top 5 processos por RAM:${NC}"
    ps aux --sort=-%mem | awk 'NR>1 && NR<=6 {printf "  %5.1f%% RAM  %5.1f%% CPU  %s\n", $4, $3, $11}' | head -5

    # Uptime
    info "Uptime: $(uptime -p)"
    echo ""
}

# ---- CLEAN ----
do_clean() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  LIMPEZA DE SISTEMA${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}\n"

    local freed=0

    # Journal logs
    local before=$(sudo journalctl --disk-usage 2>/dev/null | grep -oP '\d+(\.\d+)?[GMK]' | head -1)
    sudo journalctl --vacuum-size=500M --vacuum-time=7d 2>/dev/null
    log "Journal logs reduzido (era: ${before})"

    # APT cache
    if command -v apt-get &>/dev/null; then
        sudo apt-get clean -y 2>/dev/null
        sudo apt-get autoremove -y 2>/dev/null
        log "APT cache limpo"
    fi

    # pip cache
    if command -v pip &>/dev/null; then
        pip cache purge 2>/dev/null && log "pip cache limpo" || true
    fi

    # Browser caches
    local user_home="$HOME"
    for dir in \
        "${user_home}/.cache/mozilla/firefox/*/cache2" \
        "${user_home}/.cache/google-chrome/Default/Cache" \
        "${user_home}/.cache/opera" \
        "${user_home}/.cache/thumbnails"; do
        if [[ -d "$dir" ]]; then
            rm -rf "$dir"/* 2>/dev/null
        fi
    done
    log "Caches de navegadores limpos"

    # Old copilot logs
    find "${user_home}/.cache/github-copilot/" -name "*.log" -mtime +3 -delete 2>/dev/null
    log "Copilot logs antigos limpos"

    # VS Code workspace storage > 30 days
    find "${user_home}/.config/Code/User/workspaceStorage/" -maxdepth 1 -mindepth 1 -mtime +30 -type d 2>/dev/null | head -20 | while read -r d; do
        rm -rf "$d" 2>/dev/null
    done
    log "VS Code workspace storage antigo limpo"

    # Tmp files
    find /tmp -user "$(whoami)" -mtime +3 -delete 2>/dev/null
    log "Arquivos tmp antigos limpos"

    # Final status
    echo ""
    info "Disco após limpeza: $(df -h / | awk 'NR==2 {print $4}') livre ($(df / | awk 'NR==2 {print $5}'))"
}

# ---- TUNE ----
do_tune() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  TUNNING DE PERFORMANCE${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}\n"

    # VM parameters
    sysctl -w vm.swappiness=5 2>/dev/null
    sysctl -w vm.vfs_cache_pressure=50 2>/dev/null
    sysctl -w vm.dirty_ratio=10 2>/dev/null
    sysctl -w vm.dirty_background_ratio=5 2>/dev/null
    sysctl -w vm.dirty_expire_centisecs=1000 2>/dev/null
    sysctl -w vm.dirty_writeback_centisecs=500 2>/dev/null
    sysctl -w vm.page-cluster=0 2>/dev/null
    sysctl -w vm.min_free_kbytes=131072 2>/dev/null
    sysctl -w vm.watermark_boost_factor=0 2>/dev/null
    sysctl -w vm.watermark_scale_factor=125 2>/dev/null
    log "Parâmetros VM otimizados"

    # NVMe scheduler
    if [[ -f /sys/block/nvme0n1/queue/scheduler ]]; then
        echo "none" > /sys/block/nvme0n1/queue/scheduler 2>/dev/null
        log "NVMe scheduler: none"
    fi

    # Readahead
    if command -v blockdev &>/dev/null; then
        blockdev --setra 256 /dev/nvme0n1 2>/dev/null
        log "NVMe readahead: 256"
    fi

    # Drop caches (liberar RAM de page cache)
    local free_before=$(free -m | awk '/^Mem:/ {print $4}')
    sync
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null
    local free_after=$(free -m | awk '/^Mem:/ {print $4}')
    local gained=$((free_after - free_before))
    log "Drop caches: +${gained}MB livres"

    # Compact memory (se disponível)
    if [[ -f /proc/sys/vm/compact_memory ]]; then
        echo 1 > /proc/sys/vm/compact_memory 2>/dev/null
        log "Memória compactada"
    fi

    # Inotify watches
    echo 524288 > /proc/sys/fs/inotify/max_user_watches 2>/dev/null
    log "Inotify watches: 524288"

    echo ""
    info "RAM livre agora: $(free -h | awk '/^Mem:/ {print $4}')"
    info "Load: $(awk '{print $1, $2, $3}' /proc/loadavg)"
}

# ---- MEMORY PRESSURE ----
do_memory_relief() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  ALÍVIO DE PRESSÃO DE MEMÓRIA${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}\n"

    local ram_used_pct=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    
    if (( ram_used_pct < 80 )); then
        log "RAM em ${ram_used_pct}% — não precisa de alívio"
        return
    fi

    warn "RAM em ${ram_used_pct}% — aplicando alívio..."

    # 1. Drop page cache
    sync
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null
    log "Page cache liberado"

    # 2. Listar processos sugando mais RAM
    echo -e "\n${YELLOW}Processos consumindo mais memória:${NC}"
    ps aux --sort=-%mem | awk 'NR>1 && NR<=8 {printf "  PID %-8s %5.1f%% RAM  %s\n", $2, $4, $11}'

    # 3. Sugerir ações
    local ff_tabs=$(ps aux | grep -c 'firefox.*tab' || echo 0)
    if (( ff_tabs > 15 )); then
        warn "→ Feche abas do Firefox (${ff_tabs} abertas, recomendado: < 10)"
    fi

    local ram_after=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
    info "RAM após alívio: ${ram_after}%"
}

# ---- MAIN ----
main() {
    local action="${1:---status}"

    case "$action" in
        --status|-s)
            show_status
            ;;
        --clean|-c)
            do_clean
            ;;
        --tune|-t)
            do_tune
            ;;
        --memory|-m)
            do_memory_relief
            ;;
        --full|-f)
            do_clean
            do_tune
            show_status
            ;;
        --help|-h)
            echo "Uso: $0 [opção]"
            echo ""
            echo "Opções:"
            echo "  --status, -s   Mostrar status do sistema (default)"
            echo "  --clean,  -c   Limpar caches e lixo"
            echo "  --tune,   -t   Aplicar tunning de performance"
            echo "  --memory, -m   Alívio emergencial de memória"
            echo "  --full,   -f   Limpeza + Tunning + Status"
            echo "  --help,   -h   Mostrar esta ajuda"
            ;;
        *)
            err "Opção desconhecida: $action"
            echo "Use: $0 --help"
            exit 1
            ;;
    esac
}

main "$@"
