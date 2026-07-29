#!/usr/bin/env bash
# Orquestrador do fine-tune de tool-calling do shared-homelab (WhatsApp bot).
# Fork do padrão de scripts/trading_analyst_weekly_retrain.sh, com um passo a
# mais que o pipeline de trading não tem: o modelo é servido pela NAS
# (192.168.15.4:11436), não pelo homelab — então depois de treinar na RTX 3060
# do homelab, o GGUF precisa ser transferido e importado lá.
#
# SEGURANÇA: NUNCA promove para produção (shared-homelab.Modelfile continua
# apontando pro modelo atual até troca manual). Sempre religa ollama+coordinator
# (trap) e sempre manda um relatório Telegram (sucesso ou falha).
#
# Pré-requisitos (ver plano — rodar os passos manualmente uma vez antes de
# confiar neste script unattended, seção "Ordem de execução"):
#   - $BASE/env (venv com transformers/peft/bitsandbytes/datasets) com `mcp`
#     e `requests` também instalados (mcp_tool_bridge.py importa
#     scripts/homelab_mcp_server.py, que precisa desses dois pacotes).
#   - $BASE/llama.cpp checkout (convert_hf_to_gguf.py + llama-quantize).
#   - Acesso SSH sem senha de homelab -> NAS (192.168.15.4) para o usuário
#     que roda este script, e ambiente correspondente na NAS
#     (HOMELAB_MODELS_DIR gravável pelo usuário do Ollama).
#   - TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no ambiente (mesmo padrão do resto
#     do repo — ver reference_telegram_bot.md).
set -uo pipefail

BASE=/home/homelab/finetune
VENV="$BASE/env/bin/python"                 # transformers/peft/bitsandbytes/mcp
SYS_PY=/usr/bin/python3                     # requests/telegram (sistema)
NAS_HOST="${WHATSAPP_TOOLCALL_NAS_HOST:-root@192.168.15.4}"
NAS_MODELS_DIR="${WHATSAPP_TOOLCALL_NAS_MODELS_DIR:-/mnt/raid1/ollama}"
NAS_OLLAMA_URL="${WHATSAPP_TOOLCALL_NAS_OLLAMA_URL:-http://192.168.15.4:11436}"
CANDIDATE_TAG="shared-homelab-candidate"
LOG="$BASE/toolcall_weekly_retrain.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

echo "=== Toolcall weekly retrain start $(date) ==="
DSN=0; STATUS="OK"; FAILSTEP=""

fail() { STATUS="FALHA"; FAILSTEP="$1"; echo "!!! FALHA em: $1"; }

restore_ollama() {
  echo "--- restaurando ollama+coordinator (homelab) ---"
  sudo systemctl start ollama.service 2>/dev/null || true
  sudo systemctl start ollama-gpu-coordinator.service 2>/dev/null || true
}

send_telegram() {
  local text="$1"
  "$SYS_PY" - "$text" <<'PY' || true
import os, sys, requests
token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
if not token or not chat_id:
    print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes — pulando envio.")
    sys.exit(0)
requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data={"chat_id": chat_id, "text": sys.argv[1], "parse_mode": "Markdown"},
    timeout=15,
)
PY
}

send_report() {
  if [[ "$STATUS" == "OK" ]]; then
    send_telegram "🤖 *Retreino shared-homelab-candidate (tool-calling)*

✅ Pipeline concluído. Dataset: ${DSN} exemplos.
Candidato \`${CANDIDATE_TAG}\` importado na NAS — shadow-eval em ${BASE}/work-toolcall/shadow_eval_report.json.
Promoção continua manual (ver plano)."
  else
    send_telegram "🤖 *Retreino shared-homelab-candidate (tool-calling)*

❌ FALHA na etapa: ${FAILSTEP}
Ver ${LOG}"
  fi
}

cleanup() { restore_ollama; send_report; echo "=== Toolcall weekly retrain end $(date) status=$STATUS ==="; }
trap cleanup EXIT

# 1) Dataset sintético (não depende de Postgres — schema vem da bridge MCP)
echo "--- [1/6] dataset ---"
if "$VENV" "$(dirname "$0")/whatsapp_toolcall_dataset_builder.py" \
     --generator ollama --per-tool 45 --split 0.12 --out "$BASE/data-toolcall"; then
  DSN="$(wc -l < "$BASE/data-toolcall/whatsapp_toolcall_train.jsonl")"
  echo "dataset train: $DSN exemplos"
else
  fail "dataset"; exit 1
fi

# 2) Treino QLoRA com a 3060 livre (para ollama+coordinator; trap religa)
echo "--- [2/6] treino (pausando ollama p/ liberar 3060) ---"
sudo systemctl stop ollama-gpu-coordinator.service ollama.service && sleep 4
TRAINLOG="$BASE/work-toolcall/train_run.log"
mkdir -p "$BASE/work-toolcall"
if FT_DATASET_DIR="$BASE/data-toolcall" FT_OUTPUT_DIR="$BASE/work-toolcall" \
     CUDA_VISIBLE_DEVICES=0 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
     "$VENV" -u "$(dirname "$0")/whatsapp_toolcall_finetune_peft.py" --merge 2>&1 | tee "$TRAINLOG"; then
  echo "treino concluído"
else
  fail "treino"; restore_ollama; exit 1
fi
restore_ollama   # religa assim que o treino (uso da GPU) termina

# 3) Merged HF -> GGUF (modelo completo, não adapter — servimos standalone)
echo "--- [3/6] merged model -> GGUF ---"
if "$VENV" "$BASE/llama.cpp/convert_hf_to_gguf.py" "$BASE/work-toolcall/merged_model" \
     --outfile "$BASE/work-toolcall/candidate-f16.gguf" --outtype f16 \
   && "$BASE/llama.cpp/llama-quantize" \
     "$BASE/work-toolcall/candidate-f16.gguf" \
     "$BASE/work-toolcall/candidate-q4_k_m.gguf" Q4_K_M; then
  echo "GGUF quantizado gerado"
else
  fail "gguf"; exit 1
fi

# 4) Transferir pra NAS + `ollama create` lá (é onde o bot de fato serve o
#    modelo — ver systemd/eddie-whatsapp-bot.service.d/env.conf, OLLAMA_HOST
#    aponta pra 192.168.15.4:11436, não pro homelab).
echo "--- [4/6] transferindo GGUF pra NAS e criando modelo ---"
CANDIDATE_MODELFILE="$BASE/work-toolcall/Modelfile.candidate"
cat > "$CANDIDATE_MODELFILE" <<EOF
FROM ${NAS_MODELS_DIR}/whatsapp-toolcall-candidate.gguf
$(cat "$BASE/Modelfile.toolcall-system-suffix" 2>/dev/null || true)
PARAMETER temperature 0.7
PARAMETER num_ctx 8192
PARAMETER top_p 0.9
EOF

if scp "$BASE/work-toolcall/candidate-q4_k_m.gguf" "${NAS_HOST}:${NAS_MODELS_DIR}/whatsapp-toolcall-candidate.gguf" \
   && scp "$CANDIDATE_MODELFILE" "${NAS_HOST}:/tmp/Modelfile.candidate" \
   && ssh "$NAS_HOST" "OLLAMA_HOST=${NAS_OLLAMA_URL#http://} ollama create ${CANDIDATE_TAG} -f /tmp/Modelfile.candidate"; then
  echo "candidato ${CANDIDATE_TAG} criado na NAS"
else
  fail "nas-deploy"; exit 1
fi

# Verificação de template (ver plano seção 4/7) — não bloqueia o pipeline,
# só registra no log pra revisão humana antes da promoção manual.
ssh "$NAS_HOST" "OLLAMA_HOST=${NAS_OLLAMA_URL#http://} ollama show ${CANDIDATE_TAG} --template" \
  > "$BASE/work-toolcall/candidate_template.txt" 2>&1 || true
echo "template do candidato salvo em $BASE/work-toolcall/candidate_template.txt — comparar com 'ollama show llama3.1:8b --template' antes de promover"

# 5) Shadow-eval contra o split held-out (nunca executa ferramenta real nem
#    dispara aprovação Telegram real — puro texto-in/texto-out vs gabarito)
echo "--- [5/6] shadow-eval ---"
if "$VENV" "$(dirname "$0")/whatsapp_toolcall_shadow_eval.py" \
     --dataset "$BASE/data-toolcall/whatsapp_toolcall_test.jsonl" \
     --ollama-host "$NAS_OLLAMA_URL" --model "$CANDIDATE_TAG" \
     --out "$BASE/work-toolcall/shadow_eval_report.json"; then
  echo "shadow-eval concluído"
else
  fail "shadow"
fi

# 6) Veredito + relatório: enviado pelo trap (send_report)
echo "--- [6/6] veredito + relatório via trap ---"
echo "NUNCA promovido automaticamente — revisar shadow_eval_report.json e trocar"
echo "ollama/modelfiles/shared-homelab.Modelfile manualmente se aprovado."
exit 0
