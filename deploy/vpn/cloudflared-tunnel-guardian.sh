#!/usr/bin/env bash
# End-to-end guardian: WAN routes + cloudflared tunnel + Grafana origin.
# Conservative restarts — evita loop que causa 1033/502.
set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3002}"
GRAFANA_CONTAINER="${GRAFANA_CONTAINER:-grafana}"
CF_READY_URL="${CF_READY_URL:-http://127.0.0.1:20241/ready}"
CF_SERVICE="${CF_SERVICE:-cloudflared-rpa4all.service}"
ROUTES_SCRIPT="${ROUTES_SCRIPT:-/usr/local/sbin/cloudflared-vpn-routes.sh}"
STATE_DIR="${STATE_DIR:-/var/lib/cloudflared-tunnel-guardian}"
LOG_TAG="cloudflared-tunnel-guardian"

FAIL_THRESHOLD="${FAIL_THRESHOLD:-5}"
MAX_CF_RESTARTS_HOUR="${MAX_CF_RESTARTS_HOUR:-2}"
MAX_GRAFANA_RESTARTS_HOUR="${MAX_GRAFANA_RESTARTS_HOUR:-3}"
RESTART_COOLDOWN_SECS="${RESTART_COOLDOWN_SECS:-600}"
STARTUP_GRACE_SECS="${STARTUP_GRACE_SECS:-45}"

mkdir -p "$STATE_DIR"

log() { logger -t "$LOG_TAG" "$*"; }

read_counter() {
  local f="$1"
  cat "$f" 2>/dev/null || echo 0
}

write_counter() {
  echo "$2" > "$1"
}

rate_ok() {
  local counter_file="$1" ts_file="$2" max_hour="$3"
  local now count last_ts

  now=$(date +%s)
  count=$(read_counter "$counter_file")
  last_ts=$(read_counter "$ts_file")

  if (( now - last_ts > 3600 )); then
    count=0
  fi
  (( count < max_hour ))
}

recent_restart() {
  local ts_file="$STATE_DIR/cf_restart_ts"
  local now last_ts

  now=$(date +%s)
  last_ts=$(read_counter "$ts_file")
  (( now - last_ts < RESTART_COOLDOWN_SECS ))
}

cloudflared_in_startup() {
  local started_at now started_epoch

  started_at=$(systemctl show "$CF_SERVICE" -p ActiveEnterTimestamp --value 2>/dev/null || true)
  [[ -n "$started_at" && "$started_at" != "n/a" ]] || return 1
  started_epoch=$(date -d "$started_at" +%s 2>/dev/null || echo 0)
  (( $(date +%s) - started_epoch < STARTUP_GRACE_SECS ))
}

bump_restart() {
  local counter_file="$1" ts_file="$2"
  local now count last_ts

  now=$(date +%s)
  count=$(read_counter "$counter_file")
  last_ts=$(read_counter "$ts_file")
  if (( now - last_ts > 3600 )); then
    count=0
  fi
  count=$((count + 1))
  write_counter "$counter_file" "$count"
  write_counter "$ts_file" "$now"
  write_counter "$STATE_DIR/cf_consecutive_failures" 0
}

probe_routes() {
  [[ -x "$ROUTES_SCRIPT" ]] || return 1
  "$ROUTES_SCRIPT"
}

probe_cloudflared() {
  local resp
  resp=$(curl -sf --max-time 5 "$CF_READY_URL" 2>/dev/null) || return 1
  echo "$resp" | grep -qE '"readyConnections":([1-9]|[1-9][0-9]+)'
}

probe_grafana() {
  local resp
  resp=$(curl -sf --max-time 5 "${GRAFANA_URL}/api/health" 2>/dev/null) || return 1
  echo "$resp" | grep -qE '"database"\s*:\s*"ok"'
}

restart_cloudflared() {
  if recent_restart; then
    log "SKIP restart: cooldown ${RESTART_COOLDOWN_SECS}s ativo"
    return 1
  fi
  if ! rate_ok "$STATE_DIR/cf_restarts" "$STATE_DIR/cf_restart_ts" "$MAX_CF_RESTARTS_HOUR"; then
    log "RATE LIMIT: cloudflared restart bloqueado (${MAX_CF_RESTARTS_HOUR}/h)"
    return 1
  fi
  log "reiniciando ${CF_SERVICE} (rotas antes do restart)"
  probe_routes || true
  systemctl restart "$CF_SERVICE"
  bump_restart "$STATE_DIR/cf_restarts" "$STATE_DIR/cf_restart_ts"
  sleep "$STARTUP_GRACE_SECS"
  probe_cloudflared
}

restart_grafana() {
  if ! rate_ok "$STATE_DIR/grafana_restarts" "$STATE_DIR/grafana_restart_ts" "$MAX_GRAFANA_RESTARTS_HOUR"; then
    log "RATE LIMIT: grafana restart bloqueado"
    return 1
  fi
  log "reiniciando container ${GRAFANA_CONTAINER}"
  docker restart "$GRAFANA_CONTAINER" >/dev/null
  bump_restart "$STATE_DIR/grafana_restarts" "$STATE_DIR/grafana_restart_ts"
  sleep 10
  probe_grafana
}

cf_fail=$(read_counter "$STATE_DIR/cf_consecutive_failures")
gf_fail=$(read_counter "$STATE_DIR/grafana_consecutive_failures")

# 1) Always re-apply routes first (cheap, idempotent)
if ! probe_routes; then
  log "ERRO: falha ao aplicar rotas WAN do cloudflared"
  cf_fail=$((cf_fail + 1))
fi

# 2) Cloudflared health — never restart during startup grace
if cloudflared_in_startup; then
  log "cloudflared em startup grace (${STARTUP_GRACE_SECS}s) — skip probe/restart"
elif probe_cloudflared; then
  cf_fail=0
else
  cf_fail=$((cf_fail + 1))
  log "cloudflared unhealthy (falhas consecutivas=${cf_fail}/${FAIL_THRESHOLD})"
  if (( cf_fail >= FAIL_THRESHOLD )); then
    restart_cloudflared && cf_fail=0 || true
  fi
fi
write_counter "$STATE_DIR/cf_consecutive_failures" "$cf_fail"

# 3) Grafana origin health
if probe_grafana; then
  gf_fail=0
else
  gf_fail=$((gf_fail + 1))
  log "grafana unhealthy (falhas consecutivas=${gf_fail})"
  if (( gf_fail >= 3 )); then
    restart_grafana && gf_fail=0 || true
  fi
fi
write_counter "$STATE_DIR/grafana_consecutive_failures" "$gf_fail"

# 4) Prometheus textfile metrics
PROM_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
if [[ -d "$PROM_DIR" ]]; then
  {
    echo "# HELP cloudflared_tunnel_guardian_up 1 se rotas+tunnel+grafana OK"
    echo "# TYPE cloudflared_tunnel_guardian_up gauge"
    if (( cf_fail == 0 && gf_fail == 0 )); then echo "cloudflared_tunnel_guardian_up 1"; else echo "cloudflared_tunnel_guardian_up 0"; fi
    echo "# HELP cloudflared_tunnel_guardian_cf_failures Consecutive cloudflared probe failures"
    echo "# TYPE cloudflared_tunnel_guardian_cf_failures gauge"
    echo "cloudflared_tunnel_guardian_cf_failures ${cf_fail}"
    echo "# HELP cloudflared_tunnel_guardian_grafana_failures Consecutive grafana probe failures"
    echo "# TYPE cloudflared_tunnel_guardian_grafana_failures gauge"
    echo "cloudflared_tunnel_guardian_grafana_failures ${gf_fail}"
  } > "${PROM_DIR}/cloudflared_tunnel_guardian.prom.$$"
  mv "${PROM_DIR}/cloudflared_tunnel_guardian.prom.$$" "${PROM_DIR}/cloudflared_tunnel_guardian.prom"
fi

if (( cf_fail > 0 || gf_fail > 0 )); then
  exit 1
fi

log "OK: rotas WAN + cloudflared + grafana"