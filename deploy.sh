#!/usr/bin/env bash
# ============================================================
#  deploy.sh — Pipeline de deploy Eddie Auto-Dev
#  Uso: ./deploy.sh [OPÇÕES]
#
#  Exemplos:
#    ./deploy.sh                   # mostra help
#    ./deploy.sh clear             # deploy clear_trading_agent
#    ./deploy.sh crypto            # deploy btc_trading_agent
#    ./deploy.sh all               # todos os agentes
#    ./deploy.sh status            # status dos serviços
#    ./deploy.sh logs              # logs clear-trading-agent
#    ./deploy.sh rollback          # rollback último deploy
#    ./deploy.sh test              # apenas testes locais
# ============================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"
REMOTE_DIR="${REMOTE_DIR:-/home/homelab/eddie-auto-dev}"
VENV="${REPO_DIR}/.venv/bin"
PYTEST="${VENV}/pytest"

# ── Cores ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { printf "${CYAN}[%s]${RESET} %s\n" "$(date '+%H:%M:%S')" "$*"; }
ok()   { printf "${GREEN}✅ %s${RESET}\n" "$*"; }
warn() { printf "${YELLOW}⚠️  %s${RESET}\n" "$*"; }
fail() { printf "${RED}❌ %s${RESET}\n" "$*" >&2; exit 1; }

usage() {
    printf "${BOLD}Eddie Auto-Dev — Pipeline de Deploy${RESET}\n\n"
    printf "${YELLOW}Uso:${RESET}  %s <target> [opções]\n\n" "$0"
    printf "${YELLOW}Targets:${RESET}\n"
    printf "  ${GREEN}test${RESET}       Testes unitários locais (pytest)\n"
    printf "  ${GREEN}clear${RESET}      Deploy do clear_trading_agent\n"
    printf "  ${GREEN}crypto${RESET}     Deploy dos btc/crypto-agents\n"
    printf "  ${GREEN}all${RESET}        Deploy de todos os agentes\n"
    printf "  ${GREEN}push${RESET}       Commit + git push sem deploy\n"
    printf "  ${GREEN}status${RESET}     Status dos serviços no homelab\n"
    printf "  ${GREEN}logs${RESET}       Tail logs do clear-trading-agent\n"
    printf "  ${GREEN}logs-crypto${RESET} Tail logs dos crypto-agents\n"
    printf "  ${GREEN}rollback${RESET}   Rollback do último deploy (clear)\n"
    printf "\n${YELLOW}Variáveis:${RESET}\n"
    printf "  HOMELAB_HOST=%s  HOMELAB_USER=%s\n" "$HOMELAB_HOST" "$HOMELAB_USER"
}

# ─────────────────────────────────────────────────────────────
cmd_test() {
    log "Rodando testes unitários..."
    cd "$REPO_DIR"
    if [[ ! -x "$PYTEST" ]]; then
        fail "pytest não encontrado em $PYTEST. Rode: python3 -m venv .venv && .venv/bin/pip install pytest"
    fi
    "$PYTEST" -q --tb=short
    ok "Testes passaram"
}

cmd_push() {
    log "Sincronizando git..."
    cd "$REPO_DIR"
    # Commit se houver mudanças staged ou não staged
    if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        warn "Arquivos modificados — commitando automaticamente..."
        git add -A
        git commit -m "chore: deploy $(date '+%Y-%m-%d %H:%M')" || true
    fi
    git push origin main
    ok "Push concluído"
}

cmd_deploy_clear() {
    log "Deploy clear_trading_agent → ${HOMELAB_USER}@${HOMELAB_HOST}"
    local script="${REPO_DIR}/scripts/deploy_clear_trading_agent.sh"
    if [[ ! -f "$script" ]]; then
        fail "Script não encontrado: $script"
    fi
    bash "$script" "$HOMELAB_HOST" "$HOMELAB_USER"
    ok "clear_trading_agent implantado"
}

cmd_deploy_crypto() {
    log "Deploy btc_trading_agent → ${HOMELAB_USER}@${HOMELAB_HOST}"
    # git pull no homelab + restart dos crypto-agents
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "${HOMELAB_USER}@${HOMELAB_HOST}" bash -s <<SSH
set -euo pipefail
cd "${REMOTE_DIR}"
echo "[git] pull..."
git pull origin main --ff-only 2>&1 | tail -3

echo "[pip] instalando dependências..."
if [[ -x .venv/bin/pip ]]; then
    .venv/bin/pip install -q -r btc_trading_agent/requirements.txt 2>/dev/null || true
fi

echo "[systemd] reiniciando crypto-agents..."
sudo systemctl restart \\
    crypto-agent@BTC_USDT_aggressive \\
    crypto-agent@BTC_USDT_conservative \\
    crypto-agent@USDT_BRL_aggressive \\
    crypto-agent@USDT_BRL_conservative 2>&1 || true

sleep 3
systemctl is-active crypto-agent@BTC_USDT_aggressive >/dev/null && echo "BTC_USDT_aggressive: active" || echo "BTC_USDT_aggressive: FAILED"
systemctl is-active crypto-agent@BTC_USDT_conservative >/dev/null && echo "BTC_USDT_conservative: active" || echo "BTC_USDT_conservative: FAILED"
SSH
    ok "btc_trading_agent implantado"
}

cmd_deploy_all() {
    log "Deploy TODOS os agentes..."
    cmd_deploy_clear
    cmd_deploy_crypto
    ok "Todos os agentes implantados"
}

cmd_status() {
    log "Status dos agentes em ${HOMELAB_HOST}:"
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 \
        "${HOMELAB_USER}@${HOMELAB_HOST}" \
        "systemctl status \
            clear-trading-agent \
            crypto-agent@BTC_USDT_aggressive \
            crypto-agent@BTC_USDT_conservative \
            crypto-agent@USDT_BRL_aggressive \
            crypto-agent@USDT_BRL_conservative \
            --no-pager -n 0 2>&1 | grep -E '^(●|     Active|     Main PID)'"
}

cmd_logs() {
    local unit="${1:-clear-trading-agent}"
    log "Logs de ${unit} (Ctrl+C para sair):"
    ssh -o StrictHostKeyChecking=no "${HOMELAB_USER}@${HOMELAB_HOST}" \
        "journalctl -u '${unit}' -f -n 30"
}

cmd_rollback() {
    warn "Iniciando rollback do clear-trading-agent..."
    ssh -o StrictHostKeyChecking=no "${HOMELAB_USER}@${HOMELAB_HOST}" bash -s <<'SSH'
set -euo pipefail
if [[ -d /tmp/clear-trading-agent-backup ]]; then
    echo "Backup encontrado — revertendo..."
    sudo systemctl stop clear-trading-agent || true
    rsync -a --delete /tmp/clear-trading-agent-backup/ /home/homelab/eddie-auto-dev/
    sudo systemctl restart clear-trading-agent
    sleep 3
    if sudo systemctl is-active --quiet clear-trading-agent; then
        echo "ROLLBACK OK — serviço ativo"
    else
        echo "ROLLBACK FALHOU — serviço inativo"
        sudo journalctl -u clear-trading-agent -n 20 --no-pager
        exit 1
    fi
else
    echo "Nenhum backup disponível em /tmp/clear-trading-agent-backup"
    exit 1
fi
SSH
    ok "Rollback concluído"
}

# ─────────────────────────────────────────────────────────────
# Pipeline completo: test → push → deploy
cmd_full_pipeline() {
    local target="$1"
    printf "\n${BOLD}${CYAN}════ PIPELINE EDDIE AUTO-DEV ════${RESET}\n"
    printf "  Alvo: ${YELLOW}%s${RESET}  |  Homelab: %s@%s\n\n" "$target" "$HOMELAB_USER" "$HOMELAB_HOST"

    cmd_test

    cmd_push

    case "$target" in
        clear)   cmd_deploy_clear ;;
        crypto)  cmd_deploy_crypto ;;
        all)     cmd_deploy_all ;;
    esac

    printf "\n${BOLD}${GREEN}════ DEPLOY CONCLUÍDO ════${RESET}\n\n"
    cmd_status
}

# ─────────────────────────────────────────────────────────────
TARGET="${1:-}"

case "$TARGET" in
    test)        cmd_test ;;
    push)        cmd_push ;;
    clear)       cmd_full_pipeline clear ;;
    crypto)      cmd_full_pipeline crypto ;;
    all)         cmd_full_pipeline all ;;
    status)      cmd_status ;;
    logs)        cmd_logs "clear-trading-agent" ;;
    logs-crypto) cmd_logs "crypto-agent@*" ;;
    rollback)    cmd_rollback ;;
    "")          usage ;;
    *)           warn "Target desconhecido: $TARGET"; usage; exit 1 ;;
esac
