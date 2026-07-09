#!/usr/bin/env bash
# Configura venvs Piper (GPU0) e Kokoro no homelab para agenda diaria.
set -euo pipefail

REPO_ROOT="${1:-/home/homelab/myClaude}"
cd "$REPO_ROOT"

echo "==> Repo: $REPO_ROOT"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi nao encontrado; abortando setup GPU." >&2
  exit 1
fi

nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader

if ! command -v espeak-ng >/dev/null 2>&1; then
  echo "==> Instalando espeak-ng..."
  sudo apt-get update -qq
  sudo apt-get install -y espeak-ng
fi

echo "==> Criando venv Piper..."
python3 -m venv .venv-tts-piper
.venv-tts-piper/bin/pip install -U pip wheel
.venv-tts-piper/bin/pip install -U piper-tts
.venv-tts-piper/bin/pip uninstall -y onnxruntime 2>/dev/null || true
# Homelab tem libcudart12 (CUDA 12); onnxruntime-gpu>=1.27 exige libcudart13.
.venv-tts-piper/bin/pip install -U "onnxruntime-gpu==1.20.2"

echo "==> Criando venv Kokoro..."
python3 -m venv .venv-tts-kokoro
.venv-tts-kokoro/bin/pip install -U pip wheel
.venv-tts-kokoro/bin/pip install -U "kokoro>=0.9.4" soundfile "misaki[en]"

TORCH_INDEX="${TORCH_CUDA_INDEX:-https://download.pytorch.org/whl/cu124}"
.venv-tts-kokoro/bin/pip install -U torch --index-url "$TORCH_INDEX"

echo "==> Verificando providers ONNX (Piper)..."
.venv-tts-piper/bin/python - <<'PY'
import onnxruntime as ort
print("onnxruntime providers:", ort.get_available_providers())
assert "CUDAExecutionProvider" in ort.get_available_providers(), "CUDAExecutionProvider ausente"
PY

echo "==> Verificando torch/CUDA (Kokoro)..."
.venv-tts-kokoro/bin/python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("cuda device:", torch.cuda.get_device_name(0))
PY

echo "==> Baixando voz Piper pt_BR-faber-medium..."
mkdir -p artifacts/piper_voices
CUDA_VISIBLE_DEVICES=0 .venv-tts-piper/bin/python -m piper.download_voices pt_BR-faber-medium --data-dir artifacts/piper_voices

echo "==> Teste rapido Kokoro..."
TMP_TEXT="$(mktemp)"
TMP_WAV="$(mktemp --suffix=.wav)"
echo "Teste de voz da agenda diaria." > "$TMP_TEXT"
CUDA_VISIBLE_DEVICES=0 .venv-tts-kokoro/bin/python tools/kokoro_synth_worker.py \
  --text-file "$TMP_TEXT" \
  --output "$TMP_WAV" \
  --voice pm_santa \
  --device cuda:0
ls -la "$TMP_WAV"
rm -f "$TMP_TEXT" "$TMP_WAV"

echo "==> Setup TTS concluido com sucesso."