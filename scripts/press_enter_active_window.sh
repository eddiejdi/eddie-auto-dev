#!/usr/bin/env bash
set -euo pipefail

INTERVAL=30
WINDOW_ID=""
WORKER_MODE=0
DYNAMIC_ACTIVE=0
BACKEND=""

usage() {
  cat <<'EOF'
Uso:
  ./scripts/press_enter_active_window.sh
  ./scripts/press_enter_active_window.sh --interval 15
  ./scripts/press_enter_active_window.sh --dynamic-active

Comportamento padrão:
  - exige que a janela atualmente ativa seja do VS Code;
  - captura essa janela do VS Code;
  - abre um novo terminal;
  - nesse novo terminal, envia Enter para a janela capturada a cada N segundos.

Opções:
  --interval SEGUNDOS   Intervalo entre envios. Padrão: 30
  --dynamic-active      No worker, usa a janela ativa no momento de cada envio,
                        mas só envia Enter se ela for do VS Code
  --worker              Modo interno. Não usar manualmente.
  --window-id ID        Janela alvo no modo worker.
  --help                Exibe esta ajuda.

Dependências:
  - xdotool, ou
  - python3 com python-xlib + wmctrl
  - ambiente gráfico X11/XWayland
EOF
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Erro: comando obrigatório não encontrado: $cmd" >&2
    exit 1
  fi
}

detect_backend() {
  if command -v xdotool >/dev/null 2>&1; then
    BACKEND="xdotool"
    return
  fi

  if command -v python3 >/dev/null 2>&1 && command -v wmctrl >/dev/null 2>&1; then
    if python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("Xlib") else 1)
PY
    then
      BACKEND="python-xlib"
      return
    fi
  fi

  echo "Erro: nenhum backend disponível. Instale xdotool ou use python3 + python-xlib + wmctrl." >&2
  exit 1
}

python_xlib() {
  python3 - "$@"
}

window_exists() {
  local target_window="$1"
  case "$BACKEND" in
    xdotool)
      xdotool getwindowname "$target_window" >/dev/null 2>&1
      ;;
    python-xlib)
      python_xlib "$target_window" <<'PY' >/dev/null 2>&1
import sys
from Xlib import display, error

window_id = int(sys.argv[1], 0)
d = display.Display()
try:
    window = d.create_resource_object("window", window_id)
    window.get_attributes()
except error.XError:
    raise SystemExit(1)
raise SystemExit(0)
PY
      ;;
  esac
}

resolve_active_window() {
  case "$BACKEND" in
    xdotool)
      xdotool getactivewindow 2>/dev/null || true
      ;;
    python-xlib)
      python_xlib <<'PY' 2>/dev/null || true
from Xlib import X, display

d = display.Display()
root = d.screen().root
atom = d.intern_atom("_NET_ACTIVE_WINDOW")
prop = root.get_full_property(atom, X.AnyPropertyType)
if prop and prop.value:
    print(int(prop.value[0]))
PY
      ;;
  esac
}

get_window_class() {
  local target_window="$1"
  case "$BACKEND" in
    xdotool)
      xdotool getwindowclassname "$target_window" 2>/dev/null || true
      ;;
    python-xlib)
      python_xlib "$target_window" <<'PY' 2>/dev/null || true
import sys
from Xlib import display, error

window_id = int(sys.argv[1], 0)
d = display.Display()
try:
    window = d.create_resource_object("window", window_id)
    wm_class = window.get_wm_class() or ()
except error.XError:
    wm_class = ()

if wm_class:
    print(wm_class[-1])
PY
      ;;
  esac
}

is_vscode_window() {
  local target_window="$1"
  local window_class
  window_class="$(get_window_class "$target_window" | tr '[:upper:]' '[:lower:]')"

  case "$window_class" in
    code|code-oss|code-url-handler|codium)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

send_return_to_window() {
  local target_window="$1"

  case "$BACKEND" in
    xdotool)
      xdotool key --window "$target_window" --clearmodifiers Return
      ;;
    python-xlib)
      if ! wmctrl -i -a "$target_window" >/dev/null 2>&1; then
        return 1
      fi
      python_xlib <<'PY'
from Xlib import X, XK, display
from Xlib.ext import xtest

d = display.Display()
keysym = XK.string_to_keysym("Return")
keycode = d.keysym_to_keycode(keysym)
xtest.fake_input(d, X.KeyPress, keycode)
xtest.fake_input(d, X.KeyRelease, keycode)
d.sync()
PY
      ;;
  esac
}

launch_in_new_terminal() {
  local worker_cmd="$1"

  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "$worker_cmd"
    return
  fi

  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -lc "$worker_cmd"
    return
  fi

  if command -v konsole >/dev/null 2>&1; then
    konsole -e bash -lc "$worker_cmd"
    return
  fi

  if command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --hold -e "bash -lc '$worker_cmd'"
    return
  fi

  if command -v mate-terminal >/dev/null 2>&1; then
    mate-terminal -- bash -lc "$worker_cmd"
    return
  fi

  if command -v kitty >/dev/null 2>&1; then
    kitty bash -lc "$worker_cmd"
    return
  fi

  if command -v alacritty >/dev/null 2>&1; then
    alacritty -e bash -lc "$worker_cmd"
    return
  fi

  if command -v xterm >/dev/null 2>&1; then
    xterm -e bash -lc "$worker_cmd"
    return
  fi

  echo "Erro: nenhum terminal compatível encontrado para abrir o worker." >&2
  exit 1
}

run_worker() {
  detect_backend

  if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && [ -z "${DISPLAY:-}" ]; then
    echo "Erro: este script depende de X11/XWayland para o xdotool." >&2
    exit 1
  fi

  if [ "$DYNAMIC_ACTIVE" -eq 0 ] && [ -z "$WINDOW_ID" ]; then
    echo "Erro: --window-id é obrigatório no modo worker, exceto com --dynamic-active." >&2
    exit 1
  fi

  echo "Worker iniciado."
  echo "Backend: $BACKEND"
  echo "Intervalo: ${INTERVAL}s"
  if [ "$DYNAMIC_ACTIVE" -eq 1 ]; then
    echo "Modo: janela ativa no momento do envio, restrito ao VS Code"
  else
    echo "Janela alvo do VS Code: $WINDOW_ID"
  fi
  echo "Pressione Ctrl+C para parar."

  while true; do
    sleep "$INTERVAL"

    local target_window=""
    if [ "$DYNAMIC_ACTIVE" -eq 1 ]; then
      target_window="$(resolve_active_window)"
      if [ -z "$target_window" ]; then
        echo "Aviso: nenhuma janela ativa detectada; tentando novamente no próximo ciclo." >&2
        continue
      fi
      if ! is_vscode_window "$target_window"; then
        echo "Aviso: a janela ativa atual nao e do VS Code; Enter nao enviado neste ciclo." >&2
        continue
      fi
    else
      target_window="$WINDOW_ID"
      if ! window_exists "$target_window"; then
        echo "Erro: a janela alvo $target_window não existe mais. Encerrando." >&2
        exit 1
      fi
      if ! is_vscode_window "$target_window"; then
        echo "Erro: a janela alvo $target_window deixou de ser reconhecida como VS Code. Encerrando." >&2
        exit 1
      fi
    fi

    if send_return_to_window "$target_window"; then
      printf '[%s] Enter enviado para a janela %s\n' "$(date '+%F %T')" "$target_window"
    else
      printf '[%s] Falha ao enviar Enter para a janela %s\n' "$(date '+%F %T')" "$target_window" >&2
    fi
  done
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --interval)
      INTERVAL="${2:-}"
      shift 2
      ;;
    --window-id)
      WINDOW_ID="${2:-}"
      shift 2
      ;;
    --worker)
      WORKER_MODE=1
      shift
      ;;
    --dynamic-active)
      DYNAMIC_ACTIVE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Erro: opção desconhecida: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -le 0 ]; then
  echo "Erro: --interval deve ser um inteiro positivo." >&2
  exit 1
fi

if [ "$WORKER_MODE" -eq 1 ]; then
  run_worker
  exit 0
fi

detect_backend

if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && [ -z "${DISPLAY:-}" ]; then
  echo "Erro: este script depende de X11/XWayland para o xdotool." >&2
  exit 1
fi

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

if [ "$DYNAMIC_ACTIVE" -eq 0 ]; then
  WINDOW_ID="$(resolve_active_window)"
  if [ -z "$WINDOW_ID" ]; then
    echo "Erro: não foi possível detectar a janela ativa atual." >&2
    exit 1
  fi
  if ! is_vscode_window "$WINDOW_ID"; then
    echo "Erro: a janela ativa atual nao e do VS Code. Deixe o VS Code em foco e execute novamente." >&2
    exit 1
  fi
fi

worker_cmd=("$SCRIPT_PATH" "--worker" "--interval" "$INTERVAL")
if [ "$DYNAMIC_ACTIVE" -eq 1 ]; then
  worker_cmd+=("--dynamic-active")
else
  worker_cmd+=("--window-id" "$WINDOW_ID")
fi

printf -v worker_cmd_quoted '%q ' "${worker_cmd[@]}"

echo "Abrindo um novo terminal para executar o worker..."
if [ "$DYNAMIC_ACTIVE" -eq 0 ]; then
  echo "Janela do VS Code capturada antes da abertura do terminal: $WINDOW_ID"
fi

launch_in_new_terminal "$worker_cmd_quoted"
