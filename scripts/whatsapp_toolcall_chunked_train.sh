#!/usr/bin/env bash
# Treino QLoRA do shared-homelab em PACOTES CURTOS (default 10min, disparado
# de hora em hora por systemd timer) em vez de uma tacada de ~7h.
#
# Motivação: o treino precisa da RTX 3060, que é a mesma GPU do Ollama de
# produção (trading + bot WhatsApp). Segurar produção parada por horas não é
# aceitável; segurar por 10min de hora em hora é. Cada invocação:
#   1. para ollama+coordinator (libera a 3060)
#   2. sobe um guard em background que reforça o stop se algo externo religar
#      o ollama durante a janela de treino (ver incidente 2026-07-31: um
#      `systemctl start ollama.service` de fora, 2min30s após o pause, subiu
#      o ollama com a VRAM ainda ocupada pelo treino → CPU-fallback, e ficou
#      preso porque o restore de fim de pacote só via "systemctl start" em
#      serviço já "active" — no-op, nunca recarregava o modelo)
#   3. treina por FT_TIME_BUDGET_SECONDS, salvando checkpoint
#   4. RELIGA ollama+coordinator com stop+start forçado (nunca só "start" em
#      cima de um serviço que pode ter sido religado torto) + warmup que
#      confere VRAM real via /api/ps antes de declarar sucesso (trap EXIT —
#      sempre, mesmo em falha)
#   5. sai; a próxima invocação retoma do último checkpoint
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

# Modelo usado pro warmup de verificação pós-restart (o mesmo que produção
# usa de verdade — trading-analyst na 3060) e endpoint local do ollama.
WARMUP_MODEL="${OLLAMA_WARMUP_MODEL:-trading-analyst}"
OLLAMA_URL="${OLLAMA_LOCAL_URL:-http://localhost:11434}"
GUARD_PID=""

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

# Unidades que reergem o ollama sozinhas e brigam pela VRAM da 3060 durante
# o treino — precisam ser pausadas junto e restauradas no trap:
#   - eddie-calendar/llm-optimizer: Wants=ollama.service + Restart=always
#     (medido: eddie-calendar quebrado, em loop de restart a cada 10s, reergueu
#     o ollama 7s depois do stop).
#   - ollama-gpu-selfheal: não é Restart=always do systemd, mas o PRÓPRIO
#     script monitora "ollama down" e chama `systemctl start ollama.service`
#     de propósito (é o self-heal) — sem saber que a pausa é intencional.
#     Medido 2026-07-31: religou o ollama 2x no meio de um pacote de treino
#     ("gpu0: service down há 131s — tentando restart"); o guard deste script
#     bloqueou a tempo, mas é desperdício de ciclo e risco desnecessário.
OLLAMA_PULLERS=(eddie-calendar.service llm-optimizer.service ollama-gpu-selfheal.service)
GUARD_TRIGGERED_FLAG="$OUT_DIR/.guard_triggered"

# Enquanto o treino roda, algo fora deste script pode religar o ollama (visto
# no incidente: um `systemctl start ollama.service` externo ~2min30s após o
# pause). Esse guard mata de novo em até 15s, evitando a briga de VRAM que
# derruba o ollama pra CPU-fallback. Não identifica QUEM religou — só reage.
start_ollama_guard() {
  rm -f "$GUARD_TRIGGERED_FLAG"
  (
    while true; do
      sleep 15
      if [[ "$(systemctl is-active ollama.service 2>/dev/null || true)" == "active" ]]; then
        echo "[chunk] ⚠️ guard: algo religou ollama.service durante o treino — parando de novo"
        touch "$GUARD_TRIGGERED_FLAG"
        sudo systemctl stop ollama-gpu-coordinator.service 2>/dev/null || true
        sudo systemctl stop ollama.service 2>/dev/null || true
      fi
    done
  ) &
  GUARD_PID=$!
  disown "$GUARD_PID" 2>/dev/null || true
}

stop_ollama_guard() {
  if [[ -n "$GUARD_PID" ]]; then
    kill "$GUARD_PID" 2>/dev/null || true
    wait "$GUARD_PID" 2>/dev/null || true
    GUARD_PID=""
  fi
}

# Confere que o modelo de produção carregou de verdade na GPU (não em CPU-
# fallback) — dispara um /api/generate trivial (força load se preciso) e lê
# size_vram em /api/ps. size_vram==0 com o modelo presente = CPU-fallback.
#
# Timeout de 220s (não 90s): medido um cold-load de 171.86s do trading-analyst
# (8B Q4_K_M) logo após o treino liberar a VRAM — cache de disco frio +
# handoff de driver com a GPU recém-liberada tornam o load bem mais lento que
# um load "quente". Com 90s o script declarava CPU-fallback (e disparava
# alerta falso no Telegram) enquanto o load ainda estava em andamento e
# terminava com sucesso segundos depois, sem intervenção manual (2026-08-01).
ollama_gpu_ok() {
  curl -s -m 220 -X POST "$OLLAMA_URL/api/generate" \
    -d "{\"model\":\"$WARMUP_MODEL\",\"prompt\":\"ping\",\"stream\":false}" \
    -o /dev/null -w '' 2>/dev/null || true
  local vram
  vram="$(curl -s -m 10 "$OLLAMA_URL/api/ps" 2>/dev/null \
    | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print(0); sys.exit(0)
for m in d.get('models', []):
    if m.get('name','').split(':')[0] == '$WARMUP_MODEL'.split(':')[0]:
        print(m.get('size_vram', 0)); sys.exit(0)
print(0)
" 2>/dev/null || echo 0)"
  [[ "${vram:-0}" -gt 0 ]]
}

PAUSED=0

restore_ollama() {
  stop_ollama_guard
  if [[ "$PAUSED" != "1" ]]; then
    # Saída antes de qualquer stop (ex.: TRAINING_COMPLETE já presente, ou
    # dataset ausente) — ollama nunca foi pausado, não mexer nele.
    return 0
  fi
  echo "--- [chunk] religando ollama+coordinator+dependentes ---"
  # Stop+start forçado (nunca só "start"): se algo externo religou o ollama
  # torto durante a janela de treino, "start" em cima de um serviço já
  # "active" é um no-op e mantém o CPU-fallback — precisa derrubar e subir
  # de novo agora que a VRAM do treino já foi liberada.
  sudo systemctl stop ollama.service 2>/dev/null || true
  sleep 1
  sudo systemctl start ollama.service 2>/dev/null || true
  sleep 2
  sudo systemctl start ollama-gpu-coordinator.service 2>/dev/null || true
  for unit in "${OLLAMA_PULLERS[@]}"; do
    sudo systemctl start "$unit" 2>/dev/null || true
  done

  local st_ollama st_coord gpu_ok=0
  st_ollama="$(systemctl is-active ollama.service 2>/dev/null || true)"
  st_coord="$(systemctl is-active ollama-gpu-coordinator.service 2>/dev/null || true)"
  if [[ "$st_ollama" == "active" ]] && ollama_gpu_ok; then
    gpu_ok=1
  fi
  echo "--- [chunk] ollama=$st_ollama coordinator=$st_coord gpu_ok=$gpu_ok ---"

  if [[ "$gpu_ok" != "1" ]]; then
    echo "[chunk] ⚠️ modelo não carregou na GPU (CPU-fallback ou serviço down) — retry único"
    sudo systemctl stop ollama.service 2>/dev/null || true
    sleep 2
    sudo systemctl start ollama.service 2>/dev/null || true
    sleep 2
    st_ollama="$(systemctl is-active ollama.service 2>/dev/null || true)"
    if [[ "$st_ollama" == "active" ]] && ollama_gpu_ok; then
      gpu_ok=1
    fi
  fi

  local guard_note=""
  if [[ -f "$GUARD_TRIGGERED_FLAG" ]]; then
    guard_note="%0A%0A⚠️ Guard detectou e bloqueou ao menos 1 restart externo do ollama durante a janela de treino."
    rm -f "$GUARD_TRIGGERED_FLAG"
  fi

  if [[ "$st_ollama" != "active" ]]; then
    send_telegram "🚨 *Treino tool-calling*%0A%0AFalha ao religar ollama.service após o pacote de treino. Verificar manualmente no homelab.${guard_note}"
  elif [[ "$gpu_ok" != "1" ]]; then
    send_telegram "🚨 *Treino tool-calling*%0A%0Aollama.service religou mas *$WARMUP_MODEL* não carregou na GPU (CPU-fallback) mesmo após retry. Verificar manualmente (nvidia-smi / systemctl restart ollama.service).${guard_note}"
  elif [[ -n "$guard_note" ]]; then
    send_telegram "ℹ️ *Treino tool-calling*${guard_note}%0A%0Aollama religado normalmente ao final do pacote, GPU OK."
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

echo "--- [chunk] pausando ollama+coordinator+dependentes p/ liberar a 3060 ---"
PAUSED=1
# Ordem importa: primeiro quem reergue o ollama, depois o ollama.
for unit in "${OLLAMA_PULLERS[@]}"; do
  sudo systemctl stop "$unit" 2>/dev/null || true
done
sudo systemctl stop ollama-gpu-coordinator.service 2>/dev/null || true
sudo systemctl stop ollama.service 2>/dev/null || true
sleep 4

if [[ "$(systemctl is-active ollama.service 2>/dev/null || true)" == "active" ]]; then
  echo "[chunk] ERRO: ollama voltou a subir mesmo após o stop — abortando pacote p/ não brigar pela VRAM."
  exit 1
fi

start_ollama_guard

cd "$REPO" || exit 1
# FT_MAX_SEQ/FT_TOOLS_PER_EXAMPLE reduzidos do default (2048/6): medido
# 2026-07-31 — 45 pacotes seguidos OOM'ando na 3060 (12GB) já no 1º passo,
# "CUDA out of memory... Tried to allocate 690MB... 658MB free". Gradient
# checkpointing já está ligado por padrão (prepare_model_for_kbit_training),
# então o excesso é o tensor de logits/loss em fp32 (vocab=128k do
# Llama 3.1) escalando com o comprimento da sequência + schema das
# ferramentas embutido no prompt. 1024/4 é a mesma margem que já funciona
# nos outros pipelines (persona/trading, MAX_SEQ=1024) — ajustável via env
# se quiser tentar mais tokens numa GPU com mais VRAM livre.
FT_DATASET_DIR="$DATA_DIR" \
FT_OUTPUT_DIR="$OUT_DIR" \
FT_TIME_BUDGET_SECONDS="$BUDGET" \
FT_MAX_SEQ="${FT_MAX_SEQ:-1024}" \
FT_TOOLS_PER_EXAMPLE="${FT_TOOLS_PER_EXAMPLE:-4}" \
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
