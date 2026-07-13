#!/usr/bin/env python3
"""Worker isolado para sintese Kokoro (executado pelo venv .venv-tts-kokoro)."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sintetiza WAV com Kokoro-82M.")
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", default="pm_santa")
    parser.add_argument("--lang-code", default="p")
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = args.text_file.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Texto vazio para Kokoro.")

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    pipeline = KPipeline(lang_code=args.lang_code, device=device)
    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=args.voice):
        chunks.append(np.asarray(audio, dtype=np.float32))

    if not chunks:
        raise SystemExit("Kokoro nao gerou audio.")

    combined = np.concatenate(chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(args.output), combined, 24000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())