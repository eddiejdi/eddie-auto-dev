#!/usr/bin/env bash
# Safe deploy helper: copies config and patch files to homelab /tmp for manual review.
# Does NOT auto-apply patches unless --apply is set. Requires SSH access to homelab.

set -euo pipefail

USAGE="Usage: $0 --host HOST --user USER --apply(optional)\nCopies: patches/config_btc_recommended.json and patches/trading_agent_circuit_breaker.patch to /tmp on homelab. With --apply will back up remote config, replace config.json, and leave patch file for operator to apply."

HOST=""
USER=""
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --user) USER="$2"; shift 2;;
    --apply) APPLY=1; shift 1;;
    -h|--help) echo -e "$USAGE"; exit 0;;
    *) echo "Unknown arg: $1"; echo -e "$USAGE"; exit 2;;
  esac
done

if [[ -z "$HOST" || -z "$USER" ]]; then
  echo "--host and --user are required" >&2
  echo -e "$USAGE"
  exit 2
fi

REMOTE_TMP="/tmp/eddie_agent_patches_$(date -u +%Y%m%dT%H%M%SZ)"

echo "[INFO] Creating remote tmp dir $REMOTE_TMP on $HOST"
ssh ${USER}@${HOST} "mkdir -p ${REMOTE_TMP} && chown $(whoami) ${REMOTE_TMP} || true"

echo "[INFO] Copying local patches to ${USER}@${HOST}:${REMOTE_TMP}"
scp patches/config_btc_recommended.json ${USER}@${HOST}:${REMOTE_TMP}/config_btc_recommended.json
scp patches/trading_agent_circuit_breaker.patch ${USER}@${HOST}:${REMOTE_TMP}/trading_agent_circuit_breaker.patch
scp btc_trading_agent_recovery_postgres.sh ${USER}@${HOST}:${REMOTE_TMP}/btc_trading_agent_recovery_postgres.sh

if [[ $APPLY -eq 0 ]]; then
  echo "[INFO] Files copied. Remote path: ${REMOTE_TMP}" 
  echo "Review files on homelab and apply manually. To auto-apply, re-run with --apply (use with caution)."
  exit 0
fi

# APPLY mode: perform backups and replace config.json, but do NOT run patch automatically.
REMOTE_CONFIG="/home/homelab/myClaude/btc_trading_agent/config.json"
BACKUP_CMD="cp ${REMOTE_CONFIG} ${REMOTE_CONFIG}.bak.$(date -u +%Y%m%dT%H%M%SZ) || true"

echo "[INFO] Backing up remote config (if exists)"
ssh ${USER}@${HOST} "${BACKUP_CMD}"

echo "[INFO] Installing new config to ${REMOTE_CONFIG} (dry_run=true in config)"
ssh ${USER}@${HOST} "sudo mkdir -p $(dirname ${REMOTE_CONFIG}) && sudo chown ${USER} $(dirname ${REMOTE_CONFIG}) || true"
scp patches/config_btc_recommended.json ${USER}@${HOST}:/tmp/config_btc_recommended.json
ssh ${USER}@${HOST} "sudo mv /tmp/config_btc_recommended.json ${REMOTE_CONFIG} && sudo chown ${USER} ${REMOTE_CONFIG} && ls -l ${REMOTE_CONFIG}"

echo "[INFO] Patch file copied to ${REMOTE_TMP}/trading_agent_circuit_breaker.patch — apply manually on homelab to trading_agent.py after review."

echo "[INFO] Optionally run recovery script on homelab now (requires DB DSN)."
read -p "Run recovery script now on homelab? (y/N) " RESP
if [[ "$RESP" =~ ^[Yy]$ ]]; then
  echo "Enter DATABASE_URL for recovery (or set env on homelab):"
  read -r DSN
  ssh ${USER}@${HOST} "bash ${REMOTE_TMP}/btc_trading_agent_recovery_postgres.sh --database-url '${DSN}'"
  echo "[INFO] Recovery script executed. Check output above." 
else
  echo "[INFO] Skipping recovery execution. Review files at ${REMOTE_TMP} on homelab." 
fi

exit 0
