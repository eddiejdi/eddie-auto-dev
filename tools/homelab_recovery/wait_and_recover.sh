#!/bin/bash
# wait_and_recover.sh — aguarda homelab voltar e executa recovery automática
# Usage: nohup ./tools/homelab_recovery/wait_and_recover.sh &
# Ou:    ./tools/homelab_recovery/wait_and_recover.sh --once  (single check)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.env" 2>/dev/null || true

HOST="${HOMELAB_HOST:-192.168.15.2}"
USER="${HOMELAB_USER:-homelab}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"  # seconds between checks
MAX_WAIT="${MAX_WAIT:-86400}"           # max wait time (24h)
LOG="/tmp/homelab_wait_recovery.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

check_ping() {
  ping -c 1 -W 3 "$HOST" &>/dev/null
}

check_ssh() {
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes \
    "${USER}@${HOST}" 'echo OK' 2>/dev/null | grep -q OK
}

check_tunnel() {
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
    "https://api.rpa4all.com/agents-api/health" 2>/dev/null)
  [[ "$code" =~ ^(200|201) ]]
}

run_post_recovery() {
  log "🔧 Running post-recovery checklist..."
  if [ -f "$SCRIPT_DIR/post_recovery_checklist.sh" ]; then
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
      "${USER}@${HOST}" 'bash -s' < "$SCRIPT_DIR/post_recovery_checklist.sh" 2>&1 | tee -a "$LOG"
  fi
}

send_wol() {
  if command -v wakeonlan &>/dev/null; then
    local MAC="${HOMELAB_MAC:-d0:94:66:bb:c4:f6}"
    wakeonlan "$MAC" &>/dev/null
    wakeonlan -i 192.168.15.255 "$MAC" &>/dev/null
    log "📡 WoL packets sent to $MAC"
  fi
}

# ─── Main ───
log "⏳ Waiting for homelab ($HOST) to come back online..."
log "  Check interval: ${CHECK_INTERVAL}s, Max wait: ${MAX_WAIT}s"

STARTED=$(date +%s)
WOL_SENT=0

while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - STARTED))

  if [ "$ELAPSED" -gt "$MAX_WAIT" ]; then
    log "⏰ Max wait time exceeded (${MAX_WAIT}s). Giving up."
    exit 1
  fi

  # Send WoL every 5 minutes
  if [ $((ELAPSED % 300)) -lt "$CHECK_INTERVAL" ] && [ "$WOL_SENT" -lt $((ELAPSED / 300 + 1)) ]; then
    send_wol
    WOL_SENT=$((WOL_SENT + 1))
  fi

  # Check connectivity
  if check_ping; then
    log "🟢 Ping OK! Checking SSH..."
    sleep 5  # give services time to start

    if check_ssh; then
      log "🟢 SSH OK! Homelab is back!"
      run_post_recovery
      
      # Verify tunnel
      sleep 10
      if check_tunnel; then
        log "✅ API tunnel also responding — full recovery!"
      else
        log "⚠️  API tunnel not yet responding — services may need more time"
      fi
      
      log "🎉 Recovery complete! Elapsed: ${ELAPSED}s"
      exit 0
    else
      log "🟡 Ping OK but SSH failed — server booting or SSH down"
    fi
  else
    printf "\r[%s] Waiting... (%ds elapsed)" "$(date '+%H:%M:%S')" "$ELAPSED"
  fi

  # --once mode for single check
  if [ "$1" = "--once" ]; then
    log "Single check complete (--once mode)"
    check_ping && exit 0 || exit 1
  fi

  sleep "$CHECK_INTERVAL"
done
