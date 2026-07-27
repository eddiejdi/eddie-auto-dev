#!/usr/bin/env bash
set -euo pipefail
# watcher: cria shared-assistant, shared-coder, shared-homelab e
# shared-whatsapp quando a base de cada um estiver disponível no Ollama.
# Roda de /home/homelab/myClaude (migrado de /home/homelab/eddie-auto-dev em
# 2026-07-27). shared-homelab adicionado 2026-07-27 (2ª rodada): o próprio
# número do dono está mapeado em PHONE_MODEL_MAPPING (scripts/misc/
# whatsapp_bot.py) para "shared-homelab", sobrepondo a lógica is_owner ->
# shared-assistant — faltou nas duas primeiras varreduras.
#
# Alvo: NAS (192.168.15.4:11436), NÃO o homelab. É para lá que
# eddie-whatsapp-bot.service aponta de fato via
# systemd/eddie-whatsapp-bot.service.d/env.conf — "Persona/WhatsApp LLM na
# RTX 2060 SUPER do NAS (evita 503 da 3060 ocupada pelo trading)". A GPU1
# (1050) do homelab está descartada por outro motivo: roda lfm2.5-fast:gpu1
# com carga alta e contínua (~76 req/h) e só comporta um modelo quente por
# vez — nunca apontar estes modelos para lá.
export OLLAMA_HOST="http://192.168.15.4:11436"
REPO_DIR="/home/homelab/myClaude/ollama/modelfiles"
LOG_FILE="/var/log/watch_shared_models.log"
OLLAMA_CMD="/usr/local/bin/ollama"

:>"$LOG_FILE" 2>/dev/null || true
echo "$(date -Is) [watcher] start" >> "$LOG_FILE"

model_exists() {
  $OLLAMA_CMD list 2>/dev/null | awk '{print $1}' | grep -qE "^${1}(:|$)"
}

create_if_missing() {
  local model="$1" base="$2" modfile="$3"
  if model_exists "$model"; then
    echo "$(date -Is) [watcher] ${model} already exists" >> "$LOG_FILE"
    return
  fi
  if ! model_exists "$base"; then
    echo "$(date -Is) [watcher] base model ${base} not present, skipping ${model}" >> "$LOG_FILE"
    return
  fi
  echo "$(date -Is) [watcher] creating ${model}" >> "$LOG_FILE"
  $OLLAMA_CMD create "${model}" -f "$modfile" >> "$LOG_FILE" 2>&1 \
    || echo "$(date -Is) [watcher] create ${model} failed" >> "$LOG_FILE"
}

create_if_missing "shared-assistant" "dolphin-llama3:8b" "$REPO_DIR/shared-assistant.Modelfile"
create_if_missing "shared-coder" "llama3.1:8b" "$REPO_DIR/shared-coder-restricted.Modelfile"
create_if_missing "shared-homelab" "llama3.1:8b" "$REPO_DIR/shared-homelab.Modelfile"
create_if_missing "shared-whatsapp" "dolphin-llama3:8b" "$REPO_DIR/shared-whatsapp-trained.Modelfile"

echo "$(date -Is) [watcher] end" >> "$LOG_FILE"
