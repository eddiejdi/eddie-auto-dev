#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/disk-clean.log
LOCKFILE=/var/lock/disk-clean.lock
DRY_RUN=1
INCLUDE_DOCKER=0
DO_APT=0
DO_JOURNAL=0
TMP_DAYS=7
REPORT_ONLY=0

usage(){
  cat <<EOF
Usage: $0 [--execute] [--report-only] [--include-docker] [--apt] [--journal] [--tmp-days N]

By default runs in dry-run mode and prints planned actions. Use --execute to apply changes.
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) DRY_RUN=0; shift ;;
    --report-only) REPORT_ONLY=1; shift ;;
    --include-docker) INCLUDE_DOCKER=1; shift ;;
    --apt) DO_APT=1; shift ;;
    --journal) DO_JOURNAL=1; shift ;;
    --tmp-days) TMP_DAYS="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

mkdir -p "$(dirname "$LOG")" || true
exec 200>"$LOCKFILE"
flock -n 200 || { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Another run is active, exiting" >>"$LOG"; exit 0; }

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting disk-clean (dry-run=$DRY_RUN)" >>"$LOG"

report(){
  echo '---- Disk summary ----'
  df -h | sed -n '1,200p'
  echo
  echo 'Largest dirs under / (top 10):'
  sudo du -shx /* 2>/dev/null | sort -hr | head -n 10
  echo
  echo 'Largest files (top 20):'
  sudo find / -xdev -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -n 20 | awk '{printf "%10d %s\n", $1, $2}'
  echo
  if command -v docker >/dev/null 2>&1; then
    echo 'Docker images:'
    docker images --format ' {{.Repository}}:{{.Tag}} {{.Size}}' | sed -n '1,100p'
  fi
  if command -v journalctl >/dev/null 2>&1; then
    echo 'Journal disk usage:'
    journalctl --disk-usage || true
  fi
}

if [[ $REPORT_ONLY -eq 1 ]]; then
  report | tee -a "$LOG"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Report finished" >>"$LOG"
  exit 0
fi

# Actions
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: no changes will be made" | tee -a "$LOG"
  report | tee -a "$LOG"
else
  echo "EXECUTE: performing cleaning actions" | tee -a "$LOG"
  report | tee -a "$LOG"
fi

# Apt cleanup
if [[ $DO_APT -eq 1 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: apt-get autoremove --purge -y" | tee -a "$LOG"
  else
    echo "Running apt autoremove..." | tee -a "$LOG"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y >>"$LOG" 2>&1 || true
    sudo apt-get clean >>"$LOG" 2>&1 || true
  fi
fi

# Journal vacuum
if [[ $DO_JOURNAL -eq 1 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: journalctl --vacuum-time=7d" | tee -a "$LOG"
  else
    echo "Vacuuming journal (7 days)" | tee -a "$LOG"
    sudo journalctl --vacuum-time=${TMP_DAYS}d >>"$LOG" 2>&1 || true
  fi
fi

# Clean /tmp older than TMP_DAYS
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: find /tmp -mindepth 1 -mtime +$TMP_DAYS -print" | tee -a "$LOG"
else
  echo "Cleaning /tmp files older than $TMP_DAYS days" | tee -a "$LOG"
  sudo find /tmp -mindepth 1 -mtime +$TMP_DAYS -exec rm -rf {} + 2>>"$LOG" || true
fi

# Docker prune
if [[ $INCLUDE_DOCKER -eq 1 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: docker system prune -a --volumes --force" | tee -a "$LOG"
  else
    echo "Pruning docker..." | tee -a "$LOG"
    docker system prune -a --volumes --force >>"$LOG" 2>&1 || true
  fi
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] disk-clean finished" >>"$LOG"
exit 0
