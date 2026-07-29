#!/usr/bin/env bash
# Treino QLoRA do shared-homelab em PACOTES CURTOS (default 10min, disparado
# de hora em hora por systemd timer) em vez de uma tacada de ~7h.
#
# Motivação: o treino precisa da RTX 3060, que é a mesma GPU do Ollama de
# produção (trading + bot WhatsApp). Segurar produção parada por horas não é
# aceitável; segurar por 10min de hora em hora é. Cada invocação:
#   1. para ollama+coordinator (libera a 3060)
#   2. treina por FT_TIME_BUDGET_SECONDS, salvando checkpoint
#   3. RELIGA ollama+coordinator (trap EXIT — sempre, mesmo em falha)
#   4. sai; a próxima invocação retoma do último checkpoint
#
# Quando o treino termina (o trainer escreve TRAINING_COMPLETE no FT_OUTPUT_DIR),
# este script desabilita o próprio timer e avisa no Telegram — não fica
# reiniciando treino já concluído.
#
# Uso manual:
#   scripts/whatsapp_toolcall_chunked_train.sh
#   FT_TIME_BUDGET_SECONDS=300 scripts/whatsapp_toolcall_chunked_train.sh
set -uo pipefail

REPO="${WHATSAPP_TOOLCALL_REPO:-/home/homelab/myClaude}"
BASE="${WHATSAPP_TOOLCALL_FT_BASE:-/home/homelab/finetune}"
VENV="$BASE/env/bin/python"
DATA_DIR="${FT_DATASET_DIR:-$BASE/data-toolcall}"
OUT_DIR="${FT_OUTPUT_DIR:-$BASE/work-toolcall}"
BUDGET="${FT_TIME_BUDGET_SECONDS:-600}"
LOG="$OUT_DIR/chunked_train.log"
TIMER_UNIT="whatsapp-toolcall-chunked-train.timer"

mkdir -p "$OUT_DIR"
exec >> >(tee -a "$LOG") 2>&1

echo "=== [chunk] início $(date '+%F %T') orçamento=${BUDGET}s ==="

send_telegram() {
  local text="$1"
  /usr/bin/python3 - "$text" <<'PY' || true
import os, sys
try:
    import requests
except ImportError:
    sys.exit(0)
token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
if not token or not chat_id:
    sys.exit(0)
requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data={"chat_id": chat_id, "text": sys.argv[1], "parse_mode": "Markdown"},
    timeout=15,
)
PY
}

restore_ollama() {
  echo "--- [chunk] religando ollama+coordinator ---"
  sudo systemctl start ollama.service 2>/dev/null || true
  sleep 2
  sudo systemctl start ollama-gpu-coordinator.service 2>/dev/null || true
  local st_ollama st_coord
  st_ollama="$(systemctl is-active ollama.service 2>/dev/null || true)"
  st_coord="$(systemctl is-active ollama-gpu-coordinator.service 2>/dev/null || true)"
  echo "--- [chunk] ollama=$st_ollama coordinator=$st_coord ---"
  if [[ "$st_ollama" != "active" ]]; then
    send_telegram "🚨 *Treino tool-calling*%0A%0AFalha ao religar ollama.service após o pacote de treino. Verificar manualmente no homelab."
  fi
}
trap restore_ollama EXIT

# Já terminou? Desliga o timer e sai (idempotente — timer pode disparar de novo
# antes de alguém desabilitar na mão).
if [[ -f "$OUT_DIR/TRAINING_COMPLETE" ]]; then
  echo "[chunk] TRAINING_COMPLETE presente — nada a fazer; desabilitando timer."
  sudo systemctl disable --now "$TIMER_UNIT" 2>/dev/null || true
  exit 0
fi

if [[ ! -f "$DATA_DIR/whatsapp_toolcall_train.jsonl" ]]; then
  echo "[chunk] ERRO: dataset ausente em $DATA_DIR — rode whatsapp_toolcall_dataset_builder.py antes."
  exit 1
fi

echo "--- [chunk] pausando ollama+coordinator p/ liberar a 3060 ---"
sudo systemctl stop ollama-gpu-coordinator.service 2>/dev/null || true
sudo systemctl stop ollama.service 2>/dev/null || true
sleep 4

cd "$REPO" || exit 1
FT_DATASET_DIR="$DATA_DIR" \
FT_OUTPUT_DIR="$OUT_DIR" \
FT_TIME_BUDGET_SECONDS="$BUDGET" \
CUDA_VISIBLE_DEVICES=0 \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  "$VENV" -u scripts/whatsapp_toolcall_finetune_peft.py --merge
rc=$?

if [[ $rc -ne 0 ]]; then
  echo "[chunk] treino saiu com código $rc"
  send_telegram "⚠️ *Treino tool-calling*%0A%0APacote falhou (rc=$rc). Ver $LOG"
  exit $rc
fi

if [[ -f "$OUT_DIR/TRAINING_COMPLETE" ]]; then
  steps="$(cat "$OUT_DIR/TRAINING_COMPLETE" 2>/dev/null || echo '?')"
  echo "[chunk] ✅ treino COMPLETO ($steps) — desabilitando timer."
  sudo systemctl disable --now "$TIMER_UNIT" 2>/dev/null || true
  send_telegram "✅ *Treino tool-calling concluído*%0A%0A$steps%0A%0APróximo passo (manual): GGUF + deploy na NAS + shadow-eval. O modelo em produção NÃO foi trocado."
else
  ckpt="$(ls -d "$OUT_DIR"/lora_adapters/checkpoint-* 2>/dev/null | sort -V | tail -1 || true)"
  echo "[chunk] pacote concluído; último checkpoint: ${ckpt:-nenhum}"
fi

echo "=== [chunk] fim $(date '+%F %T') ==="
exit 0
