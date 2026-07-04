#!/usr/bin/env python3
"""Tradutor de Reuniões — serviço web (FastAPI).

Página em /static (JS) recebe o link do Meet/Teams; POST /api/join dispara o
bot Selenium que entra na sala e pede admissão. Status consultável por job.

Porta: MEETING_TRANSLATOR_PORT (default 8712).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import meet_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [meeting-translator] %(message)s")
logger = logging.getLogger("meeting_translator")

app = FastAPI(title="Tradutor de Reuniões RPA4All")
STATIC_DIR = Path(__file__).parent / "static"

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
MAX_CONCURRENT = 1  # 1 reunião por vez (capacidade avaliada do homelab)


class JoinRequest(BaseModel):
    url: str


def _active_jobs() -> int:
    with _jobs_lock:
        return sum(1 for j in _jobs.values() if j["state"] in ("iniciando", "entrando", "na_reuniao"))


def _run_job(job_id: str, url: str) -> None:
    def status(msg: str) -> None:
        with _jobs_lock:
            job = _jobs[job_id]
            job["log"].append({"t": time.strftime("%H:%M:%S"), "msg": msg})
            if "admitido" in msg:
                job["state"] = "na_reuniao"
            elif "aguardando" in msg:
                job["state"] = "entrando"
        logger.info("[%s] %s", job_id[:8], msg)

    try:
        with _jobs_lock:
            _jobs[job_id]["state"] = "entrando"
        meet_bot.join_meeting(url, status, job_id)
        with _jobs_lock:
            if _jobs[job_id]["state"] != "erro":
                _jobs[job_id]["state"] = "finalizado"
    except Exception as exc:
        logger.exception("job %s falhou", job_id[:8])
        with _jobs_lock:
            _jobs[job_id]["state"] = "erro"
            _jobs[job_id]["log"].append({"t": time.strftime("%H:%M:%S"), "msg": f"❌ {exc}"})


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/join")
def join(req: JoinRequest):
    url = req.url.strip()
    try:
        platform = meet_bot.detect_platform(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if _active_jobs() >= MAX_CONCURRENT:
        raise HTTPException(status_code=409, detail="Já existe uma reunião ativa — o homelab atende 1 por vez.")

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "url": url,
            "platform": platform,
            "state": "iniciando",
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "log": [{"t": time.strftime("%H:%M:%S"), "msg": f"job criado ({platform})"}],
        }
    threading.Thread(target=_run_job, args=(job_id, url), daemon=True, name=f"job-{job_id[:8]}").start()
    return {"job_id": job_id, "platform": platform}


@app.get("/api/jobs")
def jobs():
    with _jobs_lock:
        return sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)[:10]


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job não encontrado")
    return job


@app.get("/health")
def health():
    return {"status": "ok", "ativos": _active_jobs()}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MEETING_TRANSLATOR_PORT", "8712")))
