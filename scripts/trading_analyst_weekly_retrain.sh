#!/usr/bin/env bash
# Retreino semanal do trading-analyst-candidate (sábado à noite via systemd timer).
# Encadeia: dataset contrafactual → treino QLoRA (GPU 3060 livre) → adapter GGUF →
# ollama create → shadow-eval → veredito de rollout + relatório Telegram.
#
# SEGURANÇA: NUNCA promove para produção (só detecta/recomenda). Sempre religa
# ollama+coordinator (trap) e sempre envia um relatório (sucesso ou falha).
set -uo pipefail

BASE=/home/homelab/finetune
VENV="$BASE/env/bin/python"                       # torch/unsloth/peft/gguf
SYS_PY=/usr/bin/python3                            # psycopg2/telegram (sistema)
AGENT_PP=/apps/crypto-trader/trading/btc_trading_agent
LOG="$BASE/weekly_retrain.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

echo "=== Weekly retrain start $(date) ==="
export PYTHONPATH="$AGENT_PP"
export FT_TARGET_MODEL=trading-analyst-candidate
DBURL="$(sudo grep -E '^DATABASE_URL=' /etc/default/eddie-common | head -1 | cut -d= -f2- || true)"
export DATABASE_URL="$DBURL"
LOSS="n/d"; DSN=0; STATUS="OK"; FAILSTEP=""

fail() { STATUS="FALHA"; FAILSTEP="$1"; echo "!!! FALHA em: $1"; }

restore_ollama() {
  echo "--- restaurando ollama+coordinator ---"
  sudo systemctl start ollama.service 2>/dev/null || true
  sudo systemctl start ollama-gpu-coordinator.service 2>/dev/null || true
}
send_report() {
  # Relatório sempre — sucesso ou falha.
  if [[ "$STATUS" == "OK" ]]; then
    "$SYS_PY" "$BASE/trading_analyst_rollout_report.py" --days 8 \
      --loss "$LOSS" --dataset-n "$DSN" || echo "(falha ao enviar relatório)"
  else
    "$SYS_PY" - "$FAILSTEP" <<'PY' || true
import sys, os, asyncio
sys.path.insert(0, "/home/homelab/finetune")
from trading_analyst_rollout_report import send_telegram
step = sys.argv[1] if len(sys.argv) > 1 else "?"
asyncio.run(send_telegram(f"🤖 *Retreino trading-analyst-candidate*\n\n❌ FALHA na etapa: {step}\nVer /home/homelab/finetune/weekly_retrain.log"))
PY
  fi
}
cleanup() { restore_ollama; send_report; echo "=== Weekly retrain end $(date) status=$STATUS ==="; }
trap cleanup EXIT

# 1) Dataset contrafactual (só-leitura; python do sistema tem psycopg2)
echo "--- [1/5] dataset ---"
if "$SYS_PY" "$BASE/trading_analyst_backfill_window_dataset.py" \
     --symbol BTC-USDT --min-flat-pnl 0.10 --out "$BASE/data"; then
  cp "$BASE/data/trading_analyst_window_backfill.jsonl" "$BASE/data/trading_analyst_window.jsonl"
  DSN="$(wc -l < "$BASE/data/trading_analyst_window.jsonl")"
  echo "dataset: $DSN exemplos"
else
  fail "dataset"; exit 1
fi

# 2) Treino QLoRA com a 3060 livre (para ollama+coordinator; trap religa)
echo "--- [2/5] treino (pausando ollama p/ liberar 3060) ---"
sudo systemctl stop ollama-gpu-coordinator.service ollama.service && sleep 4
TRAINLOG="$BASE/work/train_run.log"
if FT_MAX_SEQ=512 FT_DATASET_DIR="$BASE/data" FT_OUTPUT_DIR="$BASE/work" \
     CUDA_VISIBLE_DEVICES=0 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
     "$VENV" -u "$BASE/trading_analyst_finetune_peft.py" 2>&1 | tee "$TRAINLOG"; then
  LOSS="$(grep -oE 'Loss final: [0-9.]+' "$TRAINLOG" | grep -oE '[0-9.]+' | tail -1)"
  LOSS="${LOSS:-n/d}"
else
  fail "treino"; restore_ollama; exit 1
fi
restore_ollama   # religa assim que o treino (uso da GPU) termina

# 3) Adapter → GGUF + ollama create
echo "--- [3/5] adapter GGUF + ollama create ---"
if "$VENV" "$BASE/llama.cpp/convert_lora_to_gguf.py" --base "$BASE/base_cfg" \
     --outfile "$BASE/work/candidate-adapter.gguf" --outtype f16 "$BASE/work/lora_adapters" \
   && sudo cp "$BASE/work/candidate-adapter.gguf" /mnt/raid1/ollama/candidate-adapter.gguf \
   && sudo chown ollama:ollama /mnt/raid1/ollama/candidate-adapter.gguf \
   && ollama create trading-analyst-candidate -f "$BASE/Modelfile.candidate"; then
  echo "candidato atualizado no ollama"
else
  fail "serve"; exit 1
fi

# 4) Shadow-eval nos prompts reais (psycopg2 → python do sistema)
echo "--- [4/5] shadow-eval ---"
OLLAMA_NAS_HOST=http://192.168.15.2:11434 "$SYS_PY" "$BASE/trading_analyst_shadow_eval.py" --limit 80 \
  || fail "shadow"

# 5) Veredito + relatório: enviado pelo trap (send_report) com $LOSS e $DSN
echo "--- [5/5] veredito + relatório via trap ---"
exit 0
