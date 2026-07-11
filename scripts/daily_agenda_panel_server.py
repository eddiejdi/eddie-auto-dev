#!/usr/bin/env python3
"""Painel de controle da agenda diária — backend HTTP.

Endpoints:
  GET  /                       → painel HTML
  GET  /daily_agenda_panel.js  → frontend JS
  GET  /api/status             → config + edições + job + youtube
  GET  /api/editions           → lista de edições
  GET  /api/editions/<date>    → metadados e textos
  GET  /api/editions/<date>/audio → WAV
  GET  /api/editions/<date>/video → MP4 (se existir)
  POST /api/config             → salva config parcial
  POST /api/run                → dispara pipeline
  GET  /api/job                → status do job
  POST /api/youtube/upload     → publica edição no YouTube
  GET  /api/youtube/status     → status OAuth/canal
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_DIR))

from daily_agenda_config import (  # noqa: E402
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_JOB_PATH,
    list_editions,
    load_config,
    save_config,
)
from youtube_agenda_publisher import publish_edition, youtube_auth_status  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily-agenda-panel")

HOST = os.environ.get("DAILY_AGENDA_PANEL_HOST", "0.0.0.0")
PORT = int(os.environ.get("DAILY_AGENDA_PANEL_PORT", "8093"))
API_KEY = os.environ.get("PANEL_API_KEY", "").strip()
STATIC_DIR = Path(__file__).resolve().parent / "daily_agenda_panel"
ARTIFACTS_DIR = Path(os.environ.get("DAILY_AGENDA_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS_DIR)))
JOB_LOCK = threading.Lock()


def _job_state() -> dict:
    if not DEFAULT_JOB_PATH.exists():
        return {"status": "idle"}
    return json.loads(DEFAULT_JOB_PATH.read_text(encoding="utf-8"))


def _set_job(state: dict) -> None:
    DEFAULT_JOB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_JOB_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_pipeline(payload: dict) -> None:
    cfg = load_config()
    date_str = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    mode = payload.get("mode") or cfg["defaults"]["mode"]
    quality = payload.get("quality") or cfg["defaults"]["quality"]
    dry_run = bool(payload.get("dry_run", False))
    send_telegram = bool(payload.get("send_telegram", cfg["defaults"]["send_telegram"]))
    upload_youtube = bool(payload.get("upload_youtube", cfg["defaults"]["upload_youtube"]))
    include_news = bool(payload.get("include_news", cfg["defaults"]["include_news"]))
    require_approval = bool(
        payload.get("require_approval", cfg["defaults"].get("require_approval", False))
    )
    search_cfg = cfg.get("search", {})
    deep_search = bool(payload.get("deep_search", search_cfg.get("deep_search", True)))
    timeout = int(payload.get("timeout", search_cfg.get("timeout", 45)))
    retries = int(payload.get("retries", search_cfg.get("retries", 4)))

    cmd = [
        sys.executable,
        str(TOOLS_DIR / "run_daily_agenda_broadcast.py"),
        "--date",
        date_str,
        "--mode",
        mode,
        "--quality",
        quality,
        "--timeout",
        str(timeout),
        "--retries",
        str(retries),
    ]
    if deep_search:
        cmd.append("--deep-search")
    else:
        cmd.append("--no-deep-search")
    if dry_run or not send_telegram:
        cmd.append("--dry-run")
    if not include_news:
        cmd.append("--no-news")
    chat_id = (cfg.get("telegram", {}).get("chat_id") or "").strip()
    if chat_id and send_telegram and not dry_run:
        cmd.extend(["--telegram-chat-id", chat_id])
    if require_approval and send_telegram and not dry_run:
        cmd.append("--require-approval")
    if upload_youtube and not dry_run:
        cmd.append("--upload-youtube")

    _set_job(
        {
            "status": "running",
            "phase": "broadcast",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "date": date_str,
            "command": cmd,
            "log": "",
        }
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        log_text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            _set_job(
                {
                    "status": "failed",
                    "phase": "broadcast",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "date": date_str,
                    "returncode": proc.returncode,
                    "log": log_text[-8000:],
                }
            )
            return

        youtube_result = None
        if upload_youtube and not dry_run and not require_approval:
            _set_job(
                {
                    "status": "running",
                    "phase": "youtube",
                    "date": date_str,
                    "log": log_text[-4000:],
                }
            )
            try:
                youtube_result = publish_edition(date_str, artifacts_dir=ARTIFACTS_DIR)
                youtube_payload = {
                    "video_id": youtube_result.video_id,
                    "video_url": youtube_result.video_url,
                    "title": youtube_result.title,
                }
            except Exception as exc:
                _set_job(
                    {
                        "status": "failed",
                        "phase": "youtube",
                        "finished_at": datetime.now().isoformat(timespec="seconds"),
                        "date": date_str,
                        "log": log_text[-4000:],
                        "error": str(exc),
                    }
                )
                return
        else:
            youtube_payload = None

        _set_job(
            {
                "status": "done",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "date": date_str,
                "log": log_text[-4000:],
                "youtube": youtube_payload,
            }
        )
    except Exception as exc:
        _set_job(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "date": date_str,
                "error": str(exc),
            }
        )


def _start_job(payload: dict) -> dict:
    with JOB_LOCK:
        current = _job_state()
        if current.get("status") == "running":
            return {"ok": False, "error": "Já existe um job em execução.", "job": current}
        thread = threading.Thread(target=_run_pipeline, args=(payload,), daemon=True)
        thread.start()
        return {"ok": True, "job": _job_state()}


class Handler(BaseHTTPRequestHandler):
    server_version = "DailyAgendaPanel/1.0"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict) -> None:
        self._send(
            code,
            json.dumps(obj, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _authorized(self) -> bool:
        if not API_KEY:
            return True
        return self.headers.get("X-API-KEY", "") == API_KEY

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _serve_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            self._send_json(404, {"error": f"{name} não encontrado"})
            return
        self._send(200, path.read_bytes(), content_type)

    def _edition_paths(self, date_str: str) -> dict[str, Path]:
        day_dir = ARTIFACTS_DIR / date_str
        return {
            "day_dir": day_dir,
            "source": day_dir / "source.txt",
            "locution": day_dir / "locution.txt",
            "wav": day_dir / "locution.wav",
            "mp4": day_dir / "locution.mp4",
            "meta": day_dir / "publish_meta.json",
        }

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if route == "/daily_agenda_panel.js":
            self._serve_static("daily_agenda_panel.js", "application/javascript; charset=utf-8")
            return
        if route == "/api/health":
            self._send_json(200, {"ok": True})
            return
        if route == "/api/status":
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            self._send_json(
                200,
                {
                    "config": load_config(),
                    "editions": list_editions(ARTIFACTS_DIR),
                    "job": _job_state(),
                    "youtube": youtube_auth_status(load_config()),
                },
            )
            return
        if route == "/api/editions":
            self._send_json(200, {"editions": list_editions(ARTIFACTS_DIR)})
            return
        if route == "/api/job":
            self._send_json(200, {"job": _job_state()})
            return
        if route == "/api/youtube/status":
            self._send_json(200, youtube_auth_status(load_config()))
            return
        if route.startswith("/api/editions/") and route.endswith("/audio"):
            date_str = route.split("/")[3]
            wav = self._edition_paths(date_str)["wav"]
            if not wav.exists():
                self._send_json(404, {"error": "audio não encontrado"})
                return
            self._send(200, wav.read_bytes(), "audio/wav")
            return
        if route.startswith("/api/editions/") and route.endswith("/video"):
            date_str = route.split("/")[3]
            mp4 = self._edition_paths(date_str)["mp4"]
            if not mp4.exists():
                self._send_json(404, {"error": "vídeo não encontrado"})
                return
            self._send(200, mp4.read_bytes(), "video/mp4")
            return
        if route.startswith("/api/editions/"):
            date_str = route.rstrip("/").split("/")[-1]
            paths = self._edition_paths(date_str)
            if not paths["day_dir"].exists():
                self._send_json(404, {"error": "edição não encontrada"})
                return
            meta = {}
            if paths["meta"].exists():
                meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
            self._send_json(
                200,
                {
                    "date": date_str,
                    "source": paths["source"].read_text(encoding="utf-8")
                    if paths["source"].exists()
                    else "",
                    "locution": paths["locution"].read_text(encoding="utf-8")
                    if paths["locution"].exists()
                    else "",
                    "has_wav": paths["wav"].exists(),
                    "has_mp4": paths["mp4"].exists(),
                    "meta": meta,
                },
            )
            return
        self._send_json(404, {"error": "rota desconhecida"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            payload = self._read_json()
        except Exception as exc:
            self._send_json(400, {"error": f"JSON inválido: {exc}"})
            return

        if route == "/api/config":
            current = load_config()
            merged = {**current, **payload}
            for section in ("defaults", "youtube", "telegram"):
                if section in payload and isinstance(payload[section], dict):
                    merged[section] = {**current.get(section, {}), **payload[section]}
            save_config(merged)
            self._send_json(200, {"ok": True, "config": load_config()})
            return

        if route == "/api/run":
            result = _start_job(payload)
            code = 200 if result.get("ok") else 409
            self._send_json(code, result)
            return

        if route == "/api/youtube/upload":
            date_str = payload.get("date")
            if not date_str:
                self._send_json(400, {"error": "date obrigatório"})
                return
            try:
                result = publish_edition(
                    date_str,
                    artifacts_dir=ARTIFACTS_DIR,
                    privacy_status=payload.get("privacy_status"),
                )
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "video_id": result.video_id,
                        "video_url": result.video_url,
                        "title": result.title,
                    },
                )
            except Exception as exc:
                log.error("upload youtube falhou: %s", exc)
                self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "rota desconhecida"})

    def log_message(self, fmt: str, *args) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    log.info("Painel agenda diária em http://%s:%d (auth=%s)", HOST, PORT, "on" if API_KEY else "off")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())