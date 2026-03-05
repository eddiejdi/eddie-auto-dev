#!/usr/bin/env bash
# Safe Postgres-based recovery helper for BTC trading agent
# Requires: psql in PATH and DATABASE_URL env var or pass --database-url

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [--database-url DSN] [--force-restart]

This script:
 - creates a pg_dump backup of the database
 - marks stuck OPEN trades as force_closed (only if older than 1h)
 - optionally prints recommended systemctl restart command (requires --force-restart to actually restart services)

Safety: by default it will NOT restart services; pass --force-restart to allow a restart.
EOF
}

DATABASE_URL=""
FORCE_RESTART=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --database-url) DATABASE_URL="$2"; shift 2;;
    --force-restart) FORCE_RESTART=1; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [[ -z "$DATABASE_URL" ]]; then
  DATABASE_URL=${DATABASE_URL:-}
  if [[ -z "$DATABASE_URL" ]]; then
    if [[ -n "${DATABASE_URL:-}" ]]; then
      DATABASE_URL=${DATABASE_URL}
    else
      echo "DATABASE_URL not provided. Set env or use --database-url." >&2
      usage
      exit 2
    fi
  fi
fi

# parse host for naming
TS=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_FILE="/tmp/btc_trading_backup_${TS}.dump"

echo "[INFO] Using DATABASE_URL=${DATABASE_URL}"

echo "[INFO] Creating pg_dump to ${BACKUP_FILE} (may require DB credentials via env)"
pg_dump -Fc "$DATABASE_URL" -f "$BACKUP_FILE"

echo "[INFO] Marking stuck open trades older than 1 hour as force_closed (schema=btc)"
SQL="BEGIN; SET search_path TO btc, public; UPDATE btc.trades SET status='force_closed' WHERE status='open' AND timestamp < extract(epoch from now()) - 3600 RETURNING id; COMMIT;"
psql "$DATABASE_URL" -c "$SQL"

echo "[INFO] Completed DB updates. Backup saved to ${BACKUP_FILE}"

RESTART_CMD="sudo systemctl restart crypto-agent@BTC_USDT.service"
if [[ $FORCE_RESTART -eq 1 ]]; then
  echo "[INFO] --force-restart supplied: executing restart"
  $RESTART_CMD
  echo "[INFO] Restart command executed"
else
  echo "[WARNING] Services not restarted. To restart, run:" 
  echo "         ${RESTART_CMD}"
  echo "Or re-run this script with --force-restart to allow restart."
fi

echo "[INFO] Recovery script finished. Inspect logs and Grafana before enabling live trading."
