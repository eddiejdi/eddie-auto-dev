#!/usr/bin/env bash
# Exports all Grafana dashboards from DB to provisioning JSON files.
# Triggered by grafana-dashboard-sync.service (see grafana-dashboard-sync.timer).
#
# Credentials and paths via env (or /etc/default/grafana-dashboard-sync):
#   GRAFANA_URL           default: http://localhost:3002
#   GRAFANA_USER          default: admin
#   GRAFANA_PASS          required (set in EnvironmentFile)
#   PROVISIONING_DIR      default: /home/homelab/monitoring/grafana/provisioning/dashboards

set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3002}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:?GRAFANA_PASS not set — create /etc/default/grafana-dashboard-sync}"
PROVISIONING_DIR="${PROVISIONING_DIR:-/home/homelab/monitoring/grafana/provisioning/dashboards}"
LOG_TAG="grafana-dashboard-sync"

log() { logger -t "$LOG_TAG" "$*"; }

log "Starting dashboard export → $PROVISIONING_DIR"
mkdir -p "$PROVISIONING_DIR"

# Fetch list of all DB dashboards
search=$(curl -sf -u "$GRAFANA_USER:$GRAFANA_PASS" \
    "$GRAFANA_URL/api/search?type=dash-db&limit=500") || {
    log "ERROR: could not reach Grafana at $GRAFANA_URL"
    exit 1
}

count=0
errors=0
while IFS= read -r uid; do
    [ -z "$uid" ] && continue

    dashboard=$(curl -sf -u "$GRAFANA_USER:$GRAFANA_PASS" \
        "$GRAFANA_URL/api/dashboards/uid/$uid" | \
        python3 -c "
import sys, json
data = json.load(sys.stdin)
print(json.dumps(data['dashboard'], indent=2, ensure_ascii=False))
" 2>/dev/null) || { errors=$((errors+1)); continue; }

    [ -z "$dashboard" ] && continue
    printf '%s\n' "$dashboard" > "$PROVISIONING_DIR/${uid}.json"
    count=$((count+1))
done < <(python3 -c "
import sys, json
for d in json.loads(sys.stdin.read()):
    print(d['uid'])
" <<< "$search")

log "Done: exported=$count errors=$errors target=$PROVISIONING_DIR"
[ "$errors" -gt 0 ] && exit 1 || exit 0
