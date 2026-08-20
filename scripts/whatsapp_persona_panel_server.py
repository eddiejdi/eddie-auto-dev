#!/usr/bin/env python3
"""Painel de ajuste da persona NSFW / treino WhatsApp.

Serve UI para editar artifacts/whatsapp_persona/config.json (system prompt,
temperatura, nome, few-shots) e opcionalmente rebuild do modelo Ollama na NAS.

Endpoints:
  GET  / | /whatsapp-persona/…  → HTML
  GET  /api/health
  GET  /api/config
  PUT  /api/config              → salva config (JSON body)
  POST /api/rebuild             → gera Modelfile e ollama create na NAS
  GET  /api/modelfile-preview   → preview do Modelfile a partir do config

Env:
  WA_PERSONA_PANEL_PORT=8094
  WHATSAPP_PERSONA_CONFIG=…/artifacts/whatsapp_persona/config.json
  OLLAMA_HOST=http://192.168.15.4:11436
  PANEL_API_KEY= (opcional; Authentik proxy dispensa)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wa-persona-panel")

HOST = os.environ.get("WA_PERSONA_PANEL_HOST", "0.0.0.0")
PORT = int(os.environ.get("WA_PERSONA_PANEL_PORT", "8094"))
API_KEY = os.environ.get("PANEL_API_KEY", "").strip()
REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(
    os.environ.get(
        "WHATSAPP_PERSONA_CONFIG",
        str(REPO / "artifacts" / "whatsapp_persona" / "config.json"),
    )
)
MODELFILE_PATH = Path(
    os.environ.get(
        "WHATSAPP_PERSONA_MODELFILE",
        str(REPO / "ollama" / "modelfiles" / "Modelfile.eddie-persona-free"),
    )
)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.15.4:11436").rstrip("/")
STATIC_DIR = Path(__file__).resolve().parent / "whatsapp_persona_panel"

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "model_tag": "eddie-persona-free",
    "base_model": "dolphin-llama3:8b",
    "display_name": "Persona NSFW Free",
    "persona_name": "Baldi",
    "gender": "female",
    "obedience": "extreme",
    "temperature": 0.92,
    "top_p": 0.95,
    "num_predict": 384,
    "keep_alive": "60m",
    "system_prompt": "",
    "few_shots": [],
    "notes": "",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        cfg = dict(DEFAULT_CONFIG)
        cfg["updated_at"] = _now_iso()
        return cfg
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config inválido")
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(data: dict[str, Any]) -> dict[str, Any]:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    merged["updated_at"] = _now_iso()
    # validação leve
    merged["temperature"] = float(merged.get("temperature", 0.92))
    merged["top_p"] = float(merged.get("top_p", 0.95))
    merged["num_predict"] = int(merged.get("num_predict", 384))
    if not str(merged.get("system_prompt") or "").strip():
        raise ValueError("system_prompt não pode ser vazio")
    CONFIG_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log.info("config salvo em %s", CONFIG_PATH)
    return merged


def build_modelfile(cfg: dict[str, Any]) -> str:
    system = (cfg.get("system_prompt") or "").replace('"""', "'''")
    base = cfg.get("base_model") or "dolphin-llama3:8b"
    temp = cfg.get("temperature", 0.92)
    top_p = cfg.get("top_p", 0.95)
    lines = [
        f"FROM {base}",
        "",
        f'SYSTEM """{system}',
        '"""',
        "",
        f"PARAMETER temperature {temp}",
        f"PARAMETER top_p {top_p}",
        "PARAMETER top_k 50",
        "PARAMETER num_ctx 8192",
        "PARAMETER repeat_penalty 1.05",
        "",
    ]
    for shot in cfg.get("few_shots") or []:
        if not isinstance(shot, dict):
            continue
        u = (shot.get("user") or "").replace('"""', "'''")
        a = (shot.get("assistant") or "").replace('"""', "'''")
        if not u or not a:
            continue
        lines.append(f'MESSAGE user """{u}"""')
        lines.append(f'MESSAGE assistant """{a}"""')
        lines.append("")
    return "\n".join(lines) + "\n"


def rebuild_model(cfg: dict[str, Any]) -> dict[str, Any]:
    """Escreve Modelfile e roda `ollama create` apontando ao OLLAMA_HOST."""
    modelfile = build_modelfile(cfg)
    MODELFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODELFILE_PATH.write_text(modelfile, encoding="utf-8")

    tag = cfg.get("model_tag") or "eddie-persona-free"
    # ollama CLI usa OLLAMA_HOST
    env = os.environ.copy()
    # OLLAMA_HOST no CLI é host:port sem scheme às vezes — aceita URL completa
    host = OLLAMA_HOST.replace("http://", "").replace("https://", "")
    env["OLLAMA_HOST"] = host

    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False, encoding="utf-8") as fh:
        fh.write(modelfile)
        tmp = fh.name
    try:
        proc = subprocess.run(
            ["ollama", "create", tag, "-f", tmp],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "model": tag,
            "ollama_host": OLLAMA_HOST,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-2000:],
            "modelfile_path": str(MODELFILE_PATH),
            "returncode": proc.returncode,
        }
    except FileNotFoundError:
        # sem CLI: tenta API /api/create (streaming)
        return _rebuild_via_api(tag, modelfile)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout 600s no ollama create"}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _rebuild_via_api(tag: str, modelfile: str) -> dict[str, Any]:
    payload = json.dumps({"name": tag, "modelfile": modelfile, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/create",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return {"ok": True, "model": tag, "via": "api", "body": body[:2000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "via": "api"}


class Handler(BaseHTTPRequestHandler):
    server_version = "WhatsAppPersonaPanel/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - " + fmt, self.address_string(), *args)

    def _strip_prefix(self, path: str) -> str:
        for prefix in ("/whatsapp-persona", "/whatsapp_persona", "/wa-persona"):
            if path == prefix or path.startswith(prefix + "/"):
                rest = path[len(prefix) :] or "/"
                return rest
        return path

    def _auth_ok(self) -> bool:
        if not API_KEY:
            return True
        key = self.headers.get("X-API-KEY") or self.headers.get("X-Api-Key") or ""
        if not key:
            qs = urlparse(self.path).query
            for part in qs.split("&"):
                if part.startswith("key="):
                    key = part.split("=", 1)[1]
        return key == API_KEY

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON deve ser objeto")
        return data

    def do_GET(self) -> None:
        path = self._strip_prefix(urlparse(self.path).path)
        if path in ("/api/health", "/health"):
            self._json(200, {"ok": True, "config": str(CONFIG_PATH), "ollama": OLLAMA_HOST})
            return
        if not self._auth_ok() and path.startswith("/api/"):
            self._json(401, {"error": "unauthorized"})
            return
        if path in ("/api/config",):
            try:
                self._json(200, {"config": load_config(), "path": str(CONFIG_PATH)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return
        if path in ("/api/modelfile-preview",):
            try:
                cfg = load_config()
                self._json(200, {"modelfile": build_modelfile(cfg)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return
        # static
        if path in ("/", "/index.html"):
            target = STATIC_DIR / "index.html"
        elif path.lstrip("/").endswith((".js", ".css", ".html")):
            target = STATIC_DIR / path.lstrip("/")
        else:
            target = STATIC_DIR / "index.html"
        if not target.is_file():
            self._json(404, {"error": "not found", "path": path})
            return
        ctype = "text/html; charset=utf-8"
        if target.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_PUT(self) -> None:
        path = self._strip_prefix(urlparse(self.path).path)
        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return
        if path != "/api/config":
            self._json(404, {"error": "not found"})
            return
        try:
            body = self._read_json()
            cfg = body.get("config") if "config" in body else body
            if not isinstance(cfg, dict):
                raise ValueError("body.config deve ser objeto")
            saved = save_config(cfg)
            # também sincroniza Modelfile no repo (sem create)
            MODELFILE_PATH.write_text(build_modelfile(saved), encoding="utf-8")
            self._json(200, {"ok": True, "config": saved})
        except Exception as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        path = self._strip_prefix(urlparse(self.path).path)
        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return
        if path == "/api/config":
            return self.do_PUT()
        if path != "/api/rebuild":
            self._json(404, {"error": "not found"})
            return
        try:
            body = self._read_json()
            cfg = load_config()
            if isinstance(body.get("config"), dict):
                cfg = save_config(body["config"])
            result = rebuild_model(cfg)
            self._json(200 if result.get("ok") else 500, result)
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc)})


def main() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.is_file():
        save_config(DEFAULT_CONFIG)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("WhatsApp persona panel em http://%s:%s (config=%s)", HOST, PORT, CONFIG_PATH)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
