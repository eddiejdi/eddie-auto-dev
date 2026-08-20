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
  GET  /api/job                → status do job (+ log ao vivo)
  GET  /api/job/log            → log do job (polling ?since=N)
  GET  /api/job/stream         → log em tempo real (SSE)
  POST /api/job/report         → ingestão de job externo (Telegram/systemd/workstation)
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
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_DIR))

from daily_agenda_config import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_JOB_PATH,
    default_prompt_templates,
    list_editions,
    load_config,
    load_prompt_templates,
    save_config,
)
from daily_agenda_job_status import ingest_job_report
from youtube_agenda_publisher import publish_edition, youtube_auth_status

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
JOB_LOG_PATH = Path(
    os.environ.get("DAILY_AGENDA_JOB_LOG", str(DEFAULT_ARTIFACTS_DIR / "panel_job.log"))
)
JOB_LOCK = threading.Lock()
# Bytes do log embutidos em panel_job.json (arquivo completo: panel_job.log).
JOB_LOG_JSON_TAIL = int(os.environ.get("DAILY_AGENDA_JOB_LOG_JSON_TAIL", "24000"))
# Intervalo mínimo entre gravações de status com log atualizado (s).
JOB_LOG_FLUSH_SECONDS = float(os.environ.get("DAILY_AGENDA_JOB_LOG_FLUSH_SECONDS", "0.75"))

# Job considerado zumbi se "running" além deste limite (s).
JOB_STALE_SECONDS = int(os.environ.get("DAILY_AGENDA_JOB_STALE_SECONDS", str(3 * 3600)))


def _job_state_raw() -> dict:
    if not DEFAULT_JOB_PATH.exists():
        return {"status": "idle"}
    try:
        data = json.loads(DEFAULT_JOB_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"status": "idle"}
    except Exception:
        return {"status": "idle"}


def _set_job(state: dict) -> None:
    DEFAULT_JOB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Sempre aponta o caminho do log live (se existir).
    if JOB_LOG_PATH.exists() and "log_path" not in state:
        state = {**state, "log_path": str(JOB_LOG_PATH)}
    DEFAULT_JOB_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_job_log_text(*, max_bytes: int | None = None) -> str:
    if not JOB_LOG_PATH.exists():
        return ""
    try:
        data = JOB_LOG_PATH.read_bytes()
    except OSError:
        return ""
    if max_bytes is not None and len(data) > max_bytes:
        data = data[-max_bytes:]
        # evita começar no meio de uma linha
        nl = data.find(b"\n")
        if nl != -1 and nl + 1 < len(data):
            data = data[nl + 1 :]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _job_log_size() -> int:
    try:
        return JOB_LOG_PATH.stat().st_size if JOB_LOG_PATH.exists() else 0
    except OSError:
        return 0


def _append_job_log(line: str) -> None:
    JOB_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JOB_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else line + "\n")


def _reset_job_log() -> None:
    JOB_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOB_LOG_PATH.write_text("", encoding="utf-8")


def _job_with_live_log(job: dict | None = None) -> dict:
    """Enriquece o estado do job com log ao vivo do arquivo (não só o snapshot JSON)."""
    state = dict(job or _job_state())
    live = _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL * 2)
    if live:
        state["log"] = live[-JOB_LOG_JSON_TAIL:]
        state["log_bytes"] = _job_log_size()
        state["log_path"] = str(JOB_LOG_PATH)
        state["log_live"] = True
    elif state.get("log"):
        state["log_live"] = False
    return state


def _read_log_since(offset: int, *, limit: int = 256_000) -> dict:
    """Lê bytes novos do log a partir de offset (para polling)."""
    size = _job_log_size()
    offset = max(0, int(offset or 0))
    if offset > size:
        offset = 0
    chunk = ""
    if size > offset and JOB_LOG_PATH.exists():
        with JOB_LOG_PATH.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read(limit)
        chunk = raw.decode("utf-8", errors="replace")
        offset += len(raw)
    job = _job_state()
    return {
        "ok": True,
        "offset": offset,
        "size": size,
        "chunk": chunk,
        "status": job.get("status", "idle"),
        "phase": job.get("phase"),
        "date": job.get("date"),
        "pid": job.get("pid"),
        "error": job.get("error"),
        "done": job.get("status") not in ("running",),
    }


def _pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _job_age_seconds(job: dict) -> float | None:
    started = job.get("started_at")
    if not started:
        return None
    try:
        started_dt = datetime.fromisoformat(str(started))
        return max(0.0, (datetime.now() - started_dt).total_seconds())
    except Exception:
        return None


def _heartbeat_age_seconds(job: dict) -> float | None:
    hb = job.get("heartbeat_at") or job.get("started_at")
    if not hb:
        return None
    try:
        return max(0.0, (datetime.now() - datetime.fromisoformat(str(hb))).total_seconds())
    except Exception:
        return None


def _reconcile_job_state(job: dict | None = None) -> dict:
    """Se o job está 'running' mas o processo morreu (ou expirou), marca failed."""
    state = dict(job or _job_state_raw())
    if state.get("status") != "running":
        return state

    pid = state.get("pid")
    age = _job_age_seconds(state)
    external = bool(state.get("external")) or str(state.get("source") or "") not in ("", "panel")
    # Jobs externos (Telegram/systemd/outra host) usam heartbeat, não PID local.
    if external:
        hb_age = _heartbeat_age_seconds(state)
        # 10 min sem heartbeat → falhou; ou age total absurdo.
        stale_external = (hb_age is not None and hb_age > 600) or (
            age is not None and age > JOB_STALE_SECONDS
        )
        if not stale_external:
            return state
        reason = []
        if hb_age is not None and hb_age > 600:
            reason.append(f"sem heartbeat há {int(hb_age)}s (job externo)")
        if age is not None and age > JOB_STALE_SECONDS:
            reason.append(f"expirou após {int(age)}s")
        finished_at = datetime.now().isoformat(timespec="seconds")
        state.update(
            {
                "status": "failed",
                "finished_at": finished_at,
                "error": "Job externo travado: " + "; ".join(reason or ["timeout"]),
            }
        )
        _set_job(state)
        log.warning("job externo marcado failed: %s", state.get("error"))
        return state

    alive = _pid_alive(pid) if pid else False

    # Sem PID (jobs antigos) ou PID morto → travado.
    stale_by_pid = bool(pid) and not alive
    stale_by_age = age is not None and age > JOB_STALE_SECONDS
    stale_legacy = not pid and age is not None and age > 300  # 5 min sem PID

    if not (stale_by_pid or stale_by_age or stale_legacy):
        return state

    reason = []
    if stale_by_pid:
        reason.append(f"processo pid={pid} não está mais ativo")
    if stale_by_age:
        reason.append(f"timeout ({int(age or 0)}s > {JOB_STALE_SECONDS}s)")
    if stale_legacy:
        reason.append("job legado sem pid e sem progresso")
    state.update(
        {
            "status": "failed",
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "error": "Job interrompido/travado: " + "; ".join(reason),
            "stale": True,
        }
    )
    _set_job(state)
    log.warning("job reconciliado como failed: %s", state.get("error"))
    return state


def _job_state() -> dict:
    return _reconcile_job_state()


def _clear_job(*, force: bool = False) -> dict:
    """Libera o botão Gerar boletim (marca idle/failed se stuck)."""
    with JOB_LOCK:
        current = _reconcile_job_state()
        if current.get("status") == "running" and not force:
            pid = current.get("pid")
            if _pid_alive(pid):
                return {
                    "ok": False,
                    "error": f"Job ainda em execução (pid={pid}). Use force=true para encerrar.",
                    "job": current,
                }
        # Encerra processo se force e ainda vivo
        if force and current.get("status") == "running":
            pid = current.get("pid")
            if _pid_alive(pid):
                try:
                    os.kill(int(pid), 15)
                except OSError:
                    pass
        idle = {
            "status": "idle",
            "cleared_at": datetime.now().isoformat(timespec="seconds"),
            "previous": {
                "status": current.get("status"),
                "date": current.get("date"),
                "error": current.get("error"),
            },
        }
        _set_job(idle)
        return {"ok": True, "job": idle}


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
    audio_cfg = cfg.get("audio") or {}
    min_audio = audio_cfg.get("min_duration_seconds")

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
    if min_audio is not None:
        try:
            cmd.extend(["--min-audio-seconds", str(int(min_audio))])
        except (TypeError, ValueError):
            pass

    started_at = datetime.now().isoformat(timespec="seconds")
    _reset_job_log()
    _append_job_log(f"[{started_at}] Iniciando job agenda date={date_str} quality={quality}")
    _append_job_log("$ " + " ".join(cmd))
    _set_job(
        {
            "status": "running",
            "phase": "broadcast",
            "started_at": started_at,
            "date": date_str,
            "command": cmd,
            "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
            "log_path": str(JOB_LOG_PATH),
            "log_bytes": _job_log_size(),
            "pid": None,
            "source": "panel",
            "external": False,
            "heartbeat_at": started_at,
        }
    )
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered text mode
            env=env,
        )
        _set_job(
            {
                "status": "running",
                "phase": "broadcast",
                "started_at": started_at,
                "date": date_str,
                "command": cmd,
                "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                "log_path": str(JOB_LOG_PATH),
                "log_bytes": _job_log_size(),
                "pid": proc.pid,
            }
        )

        last_flush = 0.0
        line_count = 0
        assert proc.stdout is not None
        for line in proc.stdout:
            _append_job_log(line.rstrip("\n"))
            line_count += 1
            now = time.monotonic()
            # Atualiza panel_job.json com frequência limitada (log completo no arquivo).
            if now - last_flush >= JOB_LOG_FLUSH_SECONDS or line_count <= 3:
                last_flush = now
                _set_job(
                    {
                        "status": "running",
                        "phase": "broadcast",
                        "started_at": started_at,
                        "date": date_str,
                        "command": cmd,
                        "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                        "log_path": str(JOB_LOG_PATH),
                        "log_bytes": _job_log_size(),
                        "pid": proc.pid,
                        "log_lines": line_count,
                    }
                )

        returncode = proc.wait()
        log_text = _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL)
        _append_job_log(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"processo encerrou returncode={returncode} lines={line_count}"
        )
        log_text = _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL)

        if returncode != 0:
            _set_job(
                {
                    "status": "failed",
                    "phase": "broadcast",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "date": date_str,
                    "returncode": returncode,
                    "pid": proc.pid,
                    "log": log_text[-JOB_LOG_JSON_TAIL:],
                    "log_path": str(JOB_LOG_PATH),
                    "log_bytes": _job_log_size(),
                    "log_lines": line_count,
                }
            )
            return

        youtube_result = None
        if upload_youtube and not dry_run and not require_approval:
            _append_job_log(
                f"[{datetime.now().isoformat(timespec='seconds')}] fase youtube: publicando…"
            )
            _set_job(
                {
                    "status": "running",
                    "phase": "youtube",
                    "started_at": started_at,
                    "date": date_str,
                    "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                    "log_path": str(JOB_LOG_PATH),
                    "log_bytes": _job_log_size(),
                    "pid": proc.pid,
                }
            )
            try:
                youtube_result = publish_edition(date_str, artifacts_dir=ARTIFACTS_DIR)
                youtube_payload = {
                    "video_id": youtube_result.video_id,
                    "video_url": youtube_result.video_url,
                    "title": youtube_result.title,
                }
                _append_job_log(f"YouTube OK: {youtube_result.video_url}")
            except Exception as exc:
                _append_job_log(f"YouTube ERRO: {exc}")
                _set_job(
                    {
                        "status": "failed",
                        "phase": "youtube",
                        "finished_at": datetime.now().isoformat(timespec="seconds"),
                        "date": date_str,
                        "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                        "log_path": str(JOB_LOG_PATH),
                        "log_bytes": _job_log_size(),
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
                "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                "log_path": str(JOB_LOG_PATH),
                "log_bytes": _job_log_size(),
                "log_lines": line_count,
                "youtube": youtube_payload,
            }
        )
    except Exception as exc:
        _append_job_log(f"ERRO fatal do painel: {exc}")
        _set_job(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "date": date_str,
                "error": str(exc),
                "log": _read_job_log_text(max_bytes=JOB_LOG_JSON_TAIL),
                "log_path": str(JOB_LOG_PATH),
                "log_bytes": _job_log_size(),
            }
        )


def _start_job(payload: dict) -> dict:
    with JOB_LOCK:
        current = _reconcile_job_state()
        if current.get("status") == "running":
            return {
                "ok": False,
                "error": "Já existe um job em execução. Use «Liberar botão» se estiver travado.",
                "job": current,
            }
        thread = threading.Thread(target=_run_pipeline, args=(payload,), daemon=True)
        thread.start()
        # pequeno delay para o job gravar status running
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
        if self.headers.get("X-API-KEY", "") == API_KEY:
            return True
        # EventSource / SSE não envia headers custom — aceita ?key=
        qs = parse_qs(urlparse(self.path).query)
        return (qs.get("key") or [""])[0] == API_KEY

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

    def _stream_job_log_sse(self) -> None:
        """Server-Sent Events: envia chunks do log à medida que o arquivo cresce."""
        qs = parse_qs(urlparse(self.path).query)
        try:
            offset = int((qs.get("since") or ["0"])[0] or 0)
        except ValueError:
            offset = 0
        try:
            idle_rounds_max = int((qs.get("idle") or ["120"])[0] or 120)
        except ValueError:
            idle_rounds_max = 120

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def _emit(event: str, payload: dict) -> bool:
            try:
                data = json.dumps(payload, ensure_ascii=False)
                msg = f"event: {event}\ndata: {data}\n\n".encode()
                self.wfile.write(msg)
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        idle_rounds = 0
        # Snapshot inicial
        if not _emit("hello", {"ok": True, "offset": offset, "status": _job_state().get("status")}):
            return
        while idle_rounds < idle_rounds_max:
            payload = _read_log_since(offset)
            offset = int(payload["offset"])
            if payload.get("chunk"):
                idle_rounds = 0
                if not _emit("log", payload):
                    return
            else:
                idle_rounds += 1
                if not _emit(
                    "ping",
                    {
                        "offset": offset,
                        "status": payload.get("status"),
                        "done": payload.get("done"),
                    },
                ):
                    return
            if payload.get("done") and not payload.get("chunk"):
                _emit("done", payload)
                break
            time.sleep(0.5)

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

    def do_GET(self) -> None:
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
            cfg = load_config()
            self._send_json(
                200,
                {
                    "config": cfg,
                    "prompts": load_prompt_templates(),
                    "prompt_defaults": default_prompt_templates(),
                    "editions": list_editions(ARTIFACTS_DIR),
                    "job": _job_with_live_log(),
                    "youtube": youtube_auth_status(cfg),
                },
            )
            return
        if route == "/api/prompts":
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            self._send_json(
                200,
                {
                    "prompts": load_prompt_templates(),
                    "defaults": default_prompt_templates(),
                    "placeholders": {
                        "text": "Texto-base da coleta (source.txt)",
                        "allies": "Lista de canais aliados (editorial)",
                    },
                },
            )
            return
        if route == "/api/editions":
            self._send_json(200, {"editions": list_editions(ARTIFACTS_DIR)})
            return
        if route == "/api/job":
            self._send_json(200, {"job": _job_with_live_log()})
            return
        if route == "/api/job/log":
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            qs = parse_qs(urlparse(self.path).query)
            try:
                since = int((qs.get("since") or ["0"])[0] or 0)
            except ValueError:
                since = 0
            try:
                limit = int((qs.get("limit") or ["256000"])[0] or 256000)
            except ValueError:
                limit = 256000
            limit = max(1024, min(limit, 1_000_000))
            self._send_json(200, _read_log_since(since, limit=limit))
            return
        if route == "/api/job/stream":
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            self._stream_job_log_sse()
            return
        if route == "/api/job/clear":
            # GET de conveniência (alguns clientes)
            self._send_json(200, _clear_job(force=True))
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

    def do_POST(self) -> None:
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
            try:
                current = load_config()
                merged = {**current, **payload}
                for section in (
                    "defaults",
                    "youtube",
                    "telegram",
                    "editorial",
                    "prompts",
                    "search",
                    "approval",
                    "audio",
                ):
                    if section in payload and isinstance(payload[section], dict):
                        merged[section] = {**current.get(section, {}), **payload[section]}
                # ally_youtube é lista — substitui por completo se enviada
                if "ally_youtube" in payload and isinstance(payload["ally_youtube"], list):
                    merged["ally_youtube"] = payload["ally_youtube"]
                save_config(merged)
                cfg = load_config()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "config": cfg,
                        "prompts": load_prompt_templates(),
                    },
                )
            except Exception as exc:
                log.error("POST /api/config falhou: %s", exc, exc_info=True)
                self._send_json(500, {"error": f"falha ao salvar config: {exc}"})
            return

        if route == "/api/prompts":
            # Atalho dedicado: salva só templates LLM (sem redeploy).
            try:
                prompts = payload.get("prompts") if isinstance(payload.get("prompts"), dict) else payload
                expansion = str(prompts.get("expansion_template") or "").strip()
                broadcast = str(prompts.get("broadcast_template") or "").strip()
                editor = str(prompts.get("editor_template") or "").strip()
                if not expansion or not broadcast:
                    self._send_json(
                        400,
                        {"error": "expansion_template e broadcast_template são obrigatórios"},
                    )
                    return
                current = load_config()
                prompts_out = {
                    **(current.get("prompts") or {}),
                    "expansion_template": expansion,
                    "broadcast_template": broadcast,
                }
                if editor:
                    prompts_out["editor_template"] = editor
                current["prompts"] = prompts_out
                save_config(current)
                log.info(
                    "prompts da agenda atualizados (expansion=%d, broadcast=%d, editor=%d chars)",
                    len(expansion),
                    len(broadcast),
                    len(editor),
                )
                self._send_json(
                    200,
                    {"ok": True, "prompts": load_prompt_templates()},
                )
            except Exception as exc:
                log.error("POST /api/prompts falhou: %s", exc, exc_info=True)
                self._send_json(500, {"error": f"falha ao salvar prompts: {exc}"})
            return

        if route == "/api/run":
            result = _start_job(payload)
            code = 200 if result.get("ok") else 409
            self._send_json(code, result)
            return

        if route == "/api/job/report":
            # Ingestão de jobs externos (broadcast/Telegram/workstation).
            try:
                with JOB_LOCK:
                    state = ingest_job_report(
                        payload if isinstance(payload, dict) else {},
                        artifacts_dir=ARTIFACTS_DIR,
                        job_path=DEFAULT_JOB_PATH,
                        log_path=JOB_LOG_PATH,
                    )
                self._send_json(200, {"ok": True, "job": _job_with_live_log(state)})
            except Exception as exc:
                log.error("POST /api/job/report falhou: %s", exc, exc_info=True)
                self._send_json(500, {"error": str(exc)})
            return

        if route in ("/api/job/clear", "/api/job/reset"):
            force = bool(payload.get("force", True))
            self._send_json(200, _clear_job(force=force))
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