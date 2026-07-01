#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="${TAPE_ACCESS_LOCKFILE:-/run/lock/tape-access.lock}"
STATUS_CMD="${TAPE_ACCESS_STATUS_CMD:-/usr/local/sbin/tape-access status}"
NAME=""
declare -a BUSY_UNITS=()

usage() {
    cat <<'EOF'
Uso:
  tape-session-guard --name NOME [--busy-unit UNIT]... -- COMANDO [ARGS...]

Comportamento:
  - se alguma unit informada estiver ativa, sai com observação e exit 0
  - se o lock global da fita estiver ocupado, sai com observação e exit 0
  - se a fita estiver livre, executa o comando segurando o lock exclusivo
EOF
}

log() {
    printf '%s [tape-session-guard] %s\n' "$(date -Iseconds)" "$*" >&2
}

unit_busy_state() {
    local unit="$1"
    systemctl show -p ActiveState --value "$unit" 2>/dev/null || true
}

holder_summary() {
    if [[ -x /usr/local/sbin/tape-access ]]; then
        /usr/local/sbin/tape-access status 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g'
    else
        printf 'status=indisponivel'
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)
            NAME="${2:-}"
            shift 2
            ;;
        --busy-unit)
            BUSY_UNITS+=("${2:-}")
            shift 2
            ;;
        --)
            shift
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Argumento desconhecido: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ $# -eq 0 ]]; then
    usage >&2
    exit 2
fi

for unit in "${BUSY_UNITS[@]}"; do
    [[ -n "$unit" ]] || continue
    state="$(unit_busy_state "$unit")"
    case "$state" in
        active|activating|deactivating|reloading)
            log "[OBS] sessão anterior ainda ativa em $unit (state=$state); ${NAME:-operacao} encerrada sem concorrencia."
            exit 0
            ;;
    esac
done

mkdir -p "$(dirname "$LOCKFILE")"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    log "[OBS] fita ocupada; ${NAME:-operacao} encerrada sem concorrencia. $(holder_summary)"
    exit 0
fi

export TAPE_ACCESS_ACTIVE=1
log "lock exclusivo adquirido para ${NAME:-operacao}; executando comando"
exec "$@"
