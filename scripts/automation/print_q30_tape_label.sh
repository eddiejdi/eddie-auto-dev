#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso:
  print_q30_tape_label.sh --tape-name <NOME_FITA> [opcoes]

Opcoes:
  --health <valor>          Saude da fita (ex: 100%, N/A). Padrao: N/A
  --status <valor>          Status da fita. Padrao: TESTE
  --bt-mac <mac>            MAC BLE da Q30 (padrao: DD:FE:25:83:BE:69)
  --driver-dir <path>       Diretorio do driver phomemo-q30-driver
                            (padrao: /tmp/phomemo-q30-driver)
  --python <bin>            Python a usar (padrao: /tmp/phomemo-venv/bin/python, fallback python3)
  --label-width-mm <n>      Largura da fita em mm (padrao: 12)
  --label-length-mm <n>     Comprimento da etiqueta em mm (padrao: 50)
  --font-size <n>           Tamanho da fonte (padrao: 26)
  --retries <n>             Tentativas de reconexao BLE (padrao: 5)
  --date-format <fmt>       Formato da data (padrao: %d/%m/%Y)
  --dry-run                 Mostra comando sem imprimir
  -h, --help                Ajuda

Exemplo:
  ./print_q30_tape_label.sh --tape-name SG0R26 --health 100% --status ONLINE
EOF
}

TAPE_NAME=""
HEALTH="N/A"
STATUS_TEXT="TESTE"
BT_MAC="${Q30_BT_MAC:-DD:FE:25:83:BE:69}"
DRIVER_DIR="/tmp/phomemo-q30-driver"
if [[ -x "/tmp/phomemo-venv/bin/python" ]]; then
  PYTHON_BIN="/tmp/phomemo-venv/bin/python"
else
  PYTHON_BIN="python3"
fi
LABEL_WIDTH_MM=12
LABEL_LENGTH_MM=50
FONT_SIZE=26
RETRIES=5
DATE_FMT="%d/%m/%Y"
DRY_RUN="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tape-name)
      TAPE_NAME="${2:-}"
      shift 2
      ;;
    --health)
      HEALTH="${2:-}"
      shift 2
      ;;
    --status)
      STATUS_TEXT="${2:-}"
      shift 2
      ;;
    --bt-mac)
      BT_MAC="${2:-}"
      shift 2
      ;;
    --driver-dir)
      DRIVER_DIR="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --label-width-mm)
      LABEL_WIDTH_MM="${2:-12}"
      shift 2
      ;;
    --label-length-mm)
      LABEL_LENGTH_MM="${2:-50}"
      shift 2
      ;;
    --font-size)
      FONT_SIZE="${2:-26}"
      shift 2
      ;;
    --retries)
      RETRIES="${2:-5}"
      shift 2
      ;;
    --date-format)
      DATE_FMT="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="yes"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento invalido: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$TAPE_NAME" ]]; then
  echo "Erro: informe --tape-name <NOME_FITA>" >&2
  exit 1
fi

if [[ ! -d "$DRIVER_DIR" ]]; then
  echo "Erro: diretorio do driver nao encontrado: $DRIVER_DIR" >&2
  exit 1
fi

TODAY="$(date +"$DATE_FMT")"
LABEL_TEXT="FITA: ${TAPE_NAME}
SAUDE: ${HEALTH}
STATUS: ${STATUS_TEXT}
DATA: ${TODAY}"

if [[ "$LABEL_WIDTH_MM" -ne 12 ]]; then
  echo "Aviso: o driver Q30 atual suporta largura efetiva de 12mm. Usando 12mm." >&2
  LABEL_WIDTH_MM=12
fi

echo "Etiqueta:"
echo "$LABEL_TEXT"
echo
echo "Config:"
echo "  MAC BLE: $BT_MAC"
echo "  Driver:  $DRIVER_DIR"
echo "  Python:  $PYTHON_BIN"
echo "  Fita:    ${LABEL_WIDTH_MM}x${LABEL_LENGTH_MM}mm"
echo "  Fonte:   ${FONT_SIZE}"
echo "  Retries: ${RETRIES}"

if [[ "$DRY_RUN" == "yes" ]]; then
  exit 0
fi

Q30_BT_MAC="$BT_MAC" \
Q30_DRIVER_DIR="$DRIVER_DIR" \
Q30_LABEL_TEXT="$LABEL_TEXT" \
Q30_LABEL_WIDTH_MM="$LABEL_WIDTH_MM" \
Q30_LABEL_LENGTH_MM="$LABEL_LENGTH_MM" \
Q30_FONT_SIZE="$FONT_SIZE" \
Q30_RETRIES="$RETRIES" \
"$PYTHON_BIN" -u - <<'PY'
import asyncio
import os
import sys
from PIL import Image, ImageDraw, ImageFont

driver_dir = os.environ["Q30_DRIVER_DIR"]
sys.path.insert(0, driver_dir)

from phomemo_q30 import PhomemoQ30  # noqa: E402
from image_processor import ImageProcessor  # noqa: E402
from bleak import BleakScanner  # noqa: E402

mac = os.environ["Q30_BT_MAC"]
tape_text = os.environ["Q30_LABEL_TEXT"]
width_mm = int(os.environ["Q30_LABEL_WIDTH_MM"])
length_mm = int(os.environ["Q30_LABEL_LENGTH_MM"])
font_size = int(os.environ["Q30_FONT_SIZE"])
retries = int(os.environ["Q30_RETRIES"])

# Conversao conhecida para Q30 (largura em bytes = mm * 8 / 8 = mm)
width_px_map = {12: 96}
ImageProcessor.LABEL_WIDTH_MM = width_mm
ImageProcessor.LABEL_WIDTH_PX = width_px_map.get(width_mm, 96)

img_h = ImageProcessor.LABEL_WIDTH_PX
img_w = max(320, length_mm * 8)
img = Image.new("L", (img_w, img_h), 255)
draw = ImageDraw.Draw(img)
font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
font = ImageFont.load_default()
for p in font_paths:
    if os.path.exists(p):
        font = ImageFont.truetype(p, font_size)
        break
draw.text((8, 8), tape_text, fill=0, font=font)
img_path = "/tmp/q30_tape_label.png"
img.save(img_path)

async def main():
    async def discover_targets():
        targets = []
        if mac:
            targets.append(mac.upper())
        try:
            found = await BleakScanner.discover(timeout=8.0)
            for d in found:
                name = (d.name or "").upper()
                if ("Q30" in name) or ("PHOMEMO" in name) or ("D30" in name):
                    addr = (d.address or "").upper()
                    if addr and addr not in targets:
                        targets.append(addr)
        except Exception as e:
            print(f"DISCOVERY_WARN {e}", flush=True)
        return targets

    for attempt in range(1, retries + 1):
        print(f"ATTEMPT {attempt}", flush=True)
        targets = await discover_targets()
        print("TARGETS", ",".join(targets) if targets else "NONE", flush=True)
        if not targets:
            await asyncio.sleep(2)
            continue
        for addr in targets:
            printer = PhomemoQ30(length_mm)
            ok = await printer.connect_async(addr)
            print(f"CONNECT {addr} {ok}", flush=True)
            if not ok:
                continue
            printed = await printer.print_image_async(img_path)
            print(f"PRINT {addr} {printed}", flush=True)
            await printer.disconnect_async()
            if printed:
                return 0
        await asyncio.sleep(2)
    return 1

rc = asyncio.run(main())
raise SystemExit(rc)
PY
