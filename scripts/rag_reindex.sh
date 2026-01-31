#!/usr/bin/env bash
set -euo pipefail

LOG=/var/log/rag_reindex.log
REPO_DIR="/home/homelab/eddie-auto-dev"
VENV_DIR="$REPO_DIR/.venv"
LOCKFILE=/var/lock/rag_reindex.lock

mkdir -p $(dirname "$LOG") || true
exec 200>"$LOCKFILE"
flock -n 200 || { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Another reindex is running, exiting" >>"$LOG"; exit 0; }

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting RAG reindex" >>"$LOG"

cd "$REPO_DIR"

# Use venv if present
if [[ -x "$VENV_DIR/bin/python" ]]; then
  PY="$VENV_DIR/bin/python"
else
  PY=$(command -v python3 || true)
fi

if [[ -z "$PY" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: No python available" >>"$LOG"
  exit 2
fi

# Run indexer and capture output
"$PY" index_documentation.py >>"$LOG" 2>&1 || {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: indexer failed" >>"$LOG"
  exit 2
}

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] RAG reindex finished" >>"$LOG"

exit 0
