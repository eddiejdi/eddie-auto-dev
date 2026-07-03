#!/usr/bin/env python3
"""Patch no /usr/local/bin/ollama_gpu_selfheal bash script.

Adiciona deteccao de modelos pinados com keep_alive=-1 que bloqueiam a VRAM
do GPU0 sem serem detectados pelo check de frozen original.

Causa raiz documentada (2026-05-13):
- gemma3:1b foi pinado no GPU0 com keep_alive=-1 (expires=2318)
- O selfheal original so detecta GPU "frozen" (nao responde a generate)
- Modelo pinado responde normalmente aos probes -> nunca aciona selfheal
- GPU0 fica com 0.83GB VRAM ocupada -> coordinator retorna 503 em cascata
- Agente vai para shadow mode sem DCA automatico
"""
import sys

SCRIPT_PATH = "/usr/local/bin/ollama_gpu_selfheal"

NEW_VARS = """
# --- Notificacoes Telegram (credenciais via systemd Environment) ---
TG_BOT="${TELEGRAM_BOT_TOKEN:-}"
TG_CHAT="${TELEGRAM_CHAT_ID:-}"
PINNED_EXPIRE_YEAR_THRESHOLD=2100
PINNED_CHECK_INTERVAL_SEC=60
_last_pinned_check=0
"""

# A funcao usa f-string style do bash, sem variaveis Python
NEW_FN = r"""
# --- Deteccao de modelos pinados com keep_alive=-1 ----------------
_tg_notify() {
    local msg="$1"
    [[ -z "${TG_BOT:-}" || -z "${TG_CHAT:-}" ]] && return 0
    curl -sf --max-time 5 -G \
        --data-urlencode "text=${msg}" \
        -d "chat_id=${TG_CHAT}" \
        "https://api.telegram.org/bot${TG_BOT}/sendMessage" >/dev/null 2>&1 || true
}

check_pinned_models() {
    local host="$1" gpu_name="$2"
    local now elapsed
    now=$(date +%s)
    elapsed=$(( now - _last_pinned_check ))
    (( elapsed < PINNED_CHECK_INTERVAL_SEC )) && return 0
    _last_pinned_check=$now

    local pinned_info
    pinned_info=$(curl -sf --max-time 3 "${host}/api/ps" 2>/dev/null \
        | python3 -c \
'import sys,json
from datetime import datetime
try:
    d=json.load(sys.stdin)
    for m in d.get("models",[]):
        e=m.get("expires_at","")
        if not e: continue
        try:
            yr=datetime.fromisoformat(e.replace("Z","+00:00")).year
            if yr>2100:
                vram=m.get("size_vram",0)/1024**3
                print("{0}|{1}|{2:.2f}".format(m["name"],e[:19],vram))
        except: pass
except: pass' 2>/dev/null)

    [[ -z "$pinned_info" ]] && return 0

    log "warning" "${gpu_name}: modelo(s) pinado(s) keep_alive=-1 detectado(s) -- liberando VRAM"
    local unloaded="" failed=""
    while IFS="|" read -r mname mexpires mvram; do
        [[ -z "$mname" ]] && continue
        log "warning" "${gpu_name}: descarregando ${mname} (expires=${mexpires}, VRAM=${mvram}GB)"
        if curl -sf --max-time 30 \
            -d "{\"model\":\"${mname}\",\"prompt\":\"\",\"keep_alive\":0}" \
            "${host}/api/generate" >/dev/null 2>&1; then
            log "info" "${gpu_name}: ${mname} descarregado -- GPU0 liberada"
            unloaded="${unloaded} ${mname}(${mvram}GB)"
        else
            log "crit" "${gpu_name}: FALHA ao descarregar ${mname}"
            failed="${failed} ${mname}"
        fi
    done <<< "$pinned_info"

    local ts
    ts=$(date -u "+%Y-%m-%d %H:%M UTC")
    local msg="[Ollama Selfheal] ${ts} GPU ${gpu_name}: modelo pinado corrigido.${unloaded}"
    [[ -n "$failed" ]] && msg="${msg} FALHA:${failed}"
    _tg_notify "$msg"
}

"""

ANCHOR_VARS = 'STATE_DIR="/var/lib/ollama-selfheal"\nLOG_TAG="ollama-gpu-selfheal"'
ANCHOR_FN = "# --- Loop principal -----------------------------------------------\ncheck_gpu()"
OLD_LOOP = "        # Safeguard: gerenciar real_workload se estiver consumindo GPU1 excessivamente\n        manage_real_workload || true"
NEW_LOOP = (
    "        # Detectar modelos pinados (keep_alive=-1) que bloqueiam VRAM do GPU0\n"
    "        check_pinned_models \"$GPU0_HOST\" \"gpu0\" || true\n\n"
    + OLD_LOOP
)


def main() -> int:
    with open(SCRIPT_PATH, "r") as f:
        content = f.read()

    if "check_pinned_models" in content:
        print("SKIP: patch ja aplicado")
        return 0

    anchor_v = ANCHOR_VARS.replace("\\n", "\n")
    if anchor_v not in content:
        print("ERRO: ancora STATE_DIR/LOG_TAG nao encontrada", file=sys.stderr)
        return 1
    content = content.replace(anchor_v, anchor_v + NEW_VARS)

    anchor_f = ANCHOR_FN.replace("\\n", "\n")
    if anchor_f not in content:
        print("ERRO: ancora Loop principal/check_gpu nao encontrada", file=sys.stderr)
        return 1
    content = content.replace(anchor_f, NEW_FN + anchor_f)

    if OLD_LOOP not in content:
        print("ERRO: ancora manage_real_workload nao encontrada", file=sys.stderr)
        return 1
    content = content.replace(OLD_LOOP, NEW_LOOP)

    with open(SCRIPT_PATH, "w") as f:
        f.write(content)

    assert "check_pinned_models" in content
    assert "_tg_notify" in content
    print("OK: patch aplicado com sucesso em " + SCRIPT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
