#!/usr/bin/env bash
set -euo pipefail
# watcher: cria shared-coder e shared-whatsapp quando base model estiver disponível
REPO_DIR="/home/homelab/shared-auto-dev"
BASE_MODEL="qwen2.5-coder:7b"
LOG_FILE="/var/log/watch_shared_models.log"
MODEL1="shared-coder"
MODEL2="shared-whatsapp"
MODEL1_MODFILE="$REPO_DIR/shared-coder-restricted.Modelfile"
MODEL2_MODFILE="$REPO_DIR/shared-whatsapp-trained.Modelfile"
OLLAMA_CMD="/usr/local/bin/ollama"
:>"$LOG_FILE" 2>/dev/null || true
echo "$(date -Is) [watcher] start" >> "$LOG_FILE"
# Check if base model exists
if $OLLAMA_CMD list 2>/dev/null | awk '{print $1}' | grep -qE "^${BASE_MODEL}$"; then
  echo "$(date -Is) [watcher] base model ${BASE_MODEL} present" >> "$LOG_FILE"
  # create shared-coder if missing
  if ! $OLLAMA_CMD list 2>/dev/null | awk '{print $1}' | grep -qE "^${MODEL1}(:|$)"; then
    echo "$(date -Is) [watcher] creating ${MODEL1}" >> "$LOG_FILE"
    $OLLAMA_CMD create "${MODEL1}" -f "$MODEL1_MODFILE" >> "$LOG_FILE" 2>&1 || echo "$(date -Is) [watcher] create ${MODEL1} failed" >> "$LOG_FILE"
  else
    echo "$(date -Is) [watcher] ${MODEL1} already exists" >> "$LOG_FILE"
  fi
  # create shared-whatsapp if missing
  if ! $OLLAMA_CMD list 2>/dev/null | awk '{print $1}' | grep -qE "^${MODEL2}(:|$)"; then
    echo "$(date -Is) [watcher] creating ${MODEL2}" >> "$LOG_FILE"
    $OLLAMA_CMD create "${MODEL2}" -f "$MODEL2_MODFILE" >> "$LOG_FILE" 2>&1 || echo "$(date -Is) [watcher] create ${MODEL2} failed" >> "$LOG_FILE"
  else
    echo "$(date -Is) [watcher] ${MODEL2} already exists" >> "$LOG_FILE"
  fi
else
  echo "$(date -Is) [watcher] base model ${BASE_MODEL} not present" >> "$LOG_FILE"
fi
echo "$(date -Is) [watcher] end" >> "$LOG_FILE"
