#!/usr/bin/env python3
"""API de transcrição de áudio via faster-whisper (STT local).

Política do homelab: whisper/aux só na VRAM livre — nunca despejar trading.
Por padrão roda em CPU (zero interferência na GPU0); `WHISPER_DEVICE=cuda`
liga o backend CUDA quando houver folga comprovada de VRAM.

Endpoints:
    GET  /health       → {status, model, device, compute_type, language}
    POST /transcribe   → multipart (file, language?, task?, word_timestamps?)
                         {text, language, language_probability, duration, segments}

Usage:
    uvicorn faster_whisper_api:app --host 0.0.0.0 --port 8087
"""

from __future__ import annotations

import os
import tempfile
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI(title="Faster Whisper API", version="1.0.0")

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
CACHE_DIR = os.environ.get("WHISPER_CACHE_DIR", "/home/homelab/models/whisper")

_model = None
_model_lock = None


def _get_model():
    global _model, _model_lock
    if _model is None:
        import threading

        _model_lock = threading.Lock()
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                os.makedirs(CACHE_DIR, exist_ok=True)
                _model = WhisperModel(
                    MODEL_NAME,
                    device=DEVICE,
                    compute_type=COMPUTE_TYPE,
                    download_root=CACHE_DIR,
                )
    return _model


def _run_transcription(file_path: str, language: str | None, task: str,
                       word_timestamps: bool) -> dict:
    model = _get_model()
    t0 = time.monotonic()
    segments, info = model.transcribe(
        file_path,
        language=language or None,
        task=task,
        word_timestamps=word_timestamps,
    )
    seg_list = []
    text_parts = []
    for seg in segments:
        seg_list.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        text_parts.append(seg.text.strip())
    elapsed = round(time.monotonic() - t0, 2)
    return {
        "text": " ".join(p for p in text_parts if p).strip(),
        "language": info.language,
        "language_probability": round(float(info.language_probability), 3),
        "duration": round(info.duration, 2),
        "segments": seg_list,
        "elapsed_s": elapsed,
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
    }


@app.get("/health")
def health():
    return JSONResponse({
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "cache_dir": CACHE_DIR,
    })


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    task: str = Form("transcribe"),
    word_timestamps: bool = Form(False),
):
    if task not in ("transcribe", "translate"):
        raise HTTPException(400, "task deve ser 'transcribe' ou 'translate'")
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    if suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm", ".opus", ".mp4"}:
        suffix = ".wav"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="whisper_")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(await file.read())
        try:
            result = _run_transcription(tmp_path, language, task, word_timestamps)
        except Exception as exc:
            raise HTTPException(500, f"transcrição falhou: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("WHISPER_PORT", "8087"))
    uvicorn.run(app, host=os.environ.get("WHISPER_HOST", "0.0.0.0"), port=port)
