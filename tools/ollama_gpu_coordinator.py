#!/usr/bin/env python3
"""Coordenador de GPUs Ollama — proxy HTTP inteligente de balanceamento de carga.

Redireciona requisições Ollama para GPU0 (:11434) ou GPU1 (:11435) com base na
disponibilidade e no tamanho do modelo. Usa qwen2.5:1.5b-instruct-q2_k no GPU1
como modelo de coordenação para evitar 503 em cascata.

Routing:
- Modelos pesados (>2GB): sempre GPU0 (:11434)
- Modelos leves (<1.5GB): GPU1 (:11435) primário, GPU0 como fallback
- Se GPU primário ocupado: aguarda até BUSY_WAIT_SEC e tenta o secundário

Usage:
    python3 ollama_gpu_coordinator.py --port 11437
    systemctl start ollama-gpu-coordinator

Endpoints compatíveis com Ollama:
    POST /api/generate
    POST /api/chat
    GET  /api/ps
    GET  /api/tags
    GET  /api/version
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [gpu-coord] %(message)s",
)
log = logging.getLogger("gpu-coord")

# ── Configuração ─────────────────────────────────────────────────────

GPU0_HOST = os.environ.get("OLLAMA_GPU0_HOST", "http://192.168.15.2:11434")
GPU1_HOST = os.environ.get("OLLAMA_GPU1_HOST", "http://192.168.15.2:11435")

# Modelos que DEVEM sempre ir para GPU0 (grandes, >2GB VRAM)
HEAVY_MODELS: set[str] = {
    "trading-analyst",
    "trading-analyst:latest",
    "qwen3:8b",
    "llama3.2:1b",
}

# Modelos que vão para GPU1 (leves, <1.5GB VRAM)
LIGHT_MODELS: set[str] = {
    "qwen3:0.6b",
    "qwen3-fast:gpu1",
    "qwen2.5:1.5b-instruct-q2_k",
    "qwen2.5:1.5b",
    "smollm2:iq3m",
}

# Tempo máximo aguardando GPU ficar livre (segundos)
BUSY_WAIT_SEC = int(os.environ.get("GPU_COORD_BUSY_WAIT_SEC", "10"))
# Timeout padrão de proxy de requisições (segundos)
REQUEST_TIMEOUT_SEC = int(os.environ.get("GPU_COORD_REQUEST_TIMEOUT_SEC", "180"))
# Porta padrão do coordenador
DEFAULT_PORT = int(os.environ.get("GPU_COORD_PORT", "11437"))

# ── Estado compartilhado de ocupação ─────────────────────────────────

_gpu0_requests = 0
_gpu1_requests = 0
_lock = threading.Lock()


def _is_gpu_busy(host: str) -> bool:
    """Verifica se o Ollama está processando alguma requisição."""
    try:
        req = urllib.request.Request(
            f"{host}/api/ps",
            headers={"User-Agent": "gpu-coordinator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return len(data.get("models", [])) > 0
    except Exception:
        return False  # se não responde, assume livre (tentativa direta vai falhar de qualquer modo)


def _gpu_model_count(host: str) -> int:
    """Retorna quantidade de modelos carregados na VRAM."""
    try:
        req = urllib.request.Request(
            f"{host}/api/ps",
            headers={"User-Agent": "gpu-coordinator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return len(data.get("models", []))
    except Exception:
        return 999  # erro = assume ocupado


def _route_model(model_name: str) -> tuple[str, str]:
    """Retorna (primary_host, fallback_host) para o modelo dado.

    Args:
        model_name: Nome do modelo Ollama (ex: 'trading-analyst', 'qwen3:0.6b')

    Returns:
        Tupla (primary_host, fallback_host)
    """
    name_lower = model_name.lower().split(":")[0]

    # Modelos pesados: GPU0 é sempre primário
    if model_name in HEAVY_MODELS or name_lower in {m.split(":")[0] for m in HEAVY_MODELS}:
        return GPU0_HOST, GPU1_HOST

    # Modelos leves explícitos: GPU1 é primário
    if model_name in LIGHT_MODELS or name_lower in {m.split(":")[0] for m in LIGHT_MODELS}:
        return GPU1_HOST, GPU0_HOST

    # Heurística por tamanho: modelos com sufixo 0.6b/1b/1.5b → GPU1
    for light_suffix in ("0.6b", "1b", "1.5b", "0.5b", "smol", "mini", "q2_k"):
        if light_suffix in model_name.lower():
            return GPU1_HOST, GPU0_HOST

    # Default: GPU0 para o desconhecido
    return GPU0_HOST, GPU1_HOST


def _forward_request(
    method: str,
    path: str,
    body: bytes,
    headers: dict,
    model_name: Optional[str],
) -> tuple[int, bytes, str]:
    """Encaminha a requisição ao GPU correto, com fallback.

    Returns:
        (status_code, body_bytes, chosen_host)
    """
    primary, fallback = _route_model(model_name or "")

    # Verifica se o primário está ocupado — espera até BUSY_WAIT_SEC
    waited = 0
    while waited < BUSY_WAIT_SEC and _is_gpu_busy(primary):
        log.info(f"⏳ {primary} ocupado, aguardando 2s (modelo={model_name})…")
        time.sleep(2)
        waited += 2

    # Tenta primário
    for host in (primary, fallback):
        try:
            url = f"{host}{path}"
            req = urllib.request.Request(
                url,
                data=body if body else None,
                method=method,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "gpu-coordinator/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                resp_body = resp.read()
                log.info(f"✅ {method} {path} modelo={model_name} → {host} status=200")
                return 200, resp_body, host
        except urllib.error.HTTPError as e:
            body_err = e.read() if e.fp else b""
            status = e.code
            log.warning(f"⚠️ {host}{path} HTTP {status} (modelo={model_name})")
            if status == 503 and host == primary:
                log.info(f"🔀 Tentando fallback {fallback} (modelo={model_name})")
                continue
            return status, body_err, host
        except Exception as exc:
            log.warning(f"⚠️ {host}{path} erro: {exc}")
            if host == primary:
                continue
            return 503, json.dumps({"error": str(exc)}).encode(), host

    return 503, b'{"error":"both GPUs unavailable"}', primary


class CoordinatorHandler(BaseHTTPRequestHandler):
    """Handler HTTP que atua como proxy coordenador para os Ollama GPUs."""

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        """Silencia log padrão do BaseHTTPRequestHandler."""
        pass

    def _read_body(self) -> bytes:
        """Lê o corpo da requisição HTTP."""
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _extract_model(self, body: bytes) -> Optional[str]:
        """Extrai o nome do modelo do body JSON."""
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
            return data.get("model")
        except Exception:
            return None

    def _proxy_generate_or_chat(self) -> None:
        """Processa /api/generate e /api/chat com roteamento inteligente."""
        body = self._read_body()
        model_name = self._extract_model(body)

        # Desabilita streaming para simplificar o proxy
        try:
            data = json.loads(body.decode())
            data["stream"] = False
            body = json.dumps(data).encode()
        except Exception:
            pass

        status, resp_body, host = _forward_request(
            "POST",
            self.path,
            body,
            dict(self.headers),
            model_name,
        )

        # Adiciona header indicando qual GPU atendeu
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-GPU-Host", host)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def _proxy_passthrough(self, host: str) -> None:
        """Repassa a requisição GET simples a um host fixo."""
        try:
            url = f"{host}{self.path}"
            req = urllib.request.Request(url, headers={"User-Agent": "gpu-coordinator/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except Exception as exc:
            err = json.dumps({"error": str(exc)}).encode()
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def _handle_ps(self) -> None:
        """Agrega /api/ps de ambos os GPUs."""
        models: list = []
        for host in (GPU0_HOST, GPU1_HOST):
            try:
                req = urllib.request.Request(
                    f"{host}/api/ps",
                    headers={"User-Agent": "gpu-coordinator/1.0"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    models.extend(data.get("models", []))
            except Exception:
                pass
        body = json.dumps({"models": models}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_tags(self) -> None:
        """Agrega /api/tags de ambos os GPUs (sem duplicatas)."""
        seen: set[str] = set()
        models: list = []
        for host in (GPU0_HOST, GPU1_HOST):
            try:
                req = urllib.request.Request(
                    f"{host}/api/tags",
                    headers={"User-Agent": "gpu-coordinator/1.0"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    for m in data.get("models", []):
                        if m["name"] not in seen:
                            seen.add(m["name"])
                            models.append(m)
            except Exception:
                pass
        body = json.dumps({"models": models}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_health(self) -> None:
        """Endpoint de health com status dos GPUs."""
        gpu0_busy = _is_gpu_busy(GPU0_HOST)
        gpu1_busy = _is_gpu_busy(GPU1_HOST)
        body = json.dumps({
            "coordinator": "ok",
            "gpu0": {"host": GPU0_HOST, "busy": gpu0_busy},
            "gpu1": {"host": GPU1_HOST, "busy": gpu1_busy},
            "routing": {
                "heavy_models_to": "GPU0",
                "light_models_to": "GPU1",
                "coordinator_model": "qwen2.5:1.5b-instruct-q2_k",
            },
        }, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Trata GET: /api/ps, /api/tags, /api/version, /health."""
        if self.path == "/api/ps":
            self._handle_ps()
        elif self.path.startswith("/api/tags"):
            self._handle_tags()
        elif self.path == "/health":
            self._handle_health()
        else:
            self._proxy_passthrough(GPU0_HOST)

    def do_POST(self) -> None:
        """Trata POST: /api/generate, /api/chat."""
        if self.path in ("/api/generate", "/api/chat"):
            self._proxy_generate_or_chat()
        else:
            # Outros endpoints (pull, push, etc.) → GPU0
            body = self._read_body()
            status, resp_body, _ = _forward_request("POST", self.path, body, {}, None)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)


def main() -> None:
    """Ponto de entrada do coordenador."""
    parser = argparse.ArgumentParser(description="Coordenador de GPUs Ollama")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--gpu0", default=GPU0_HOST)
    parser.add_argument("--gpu1", default=GPU1_HOST)
    args = parser.parse_args()

    # pylint: disable=global-statement
    import sys as _sys
    _mod = _sys.modules[__name__]
    setattr(_mod, "GPU0_HOST", args.gpu0)
    setattr(_mod, "GPU1_HOST", args.gpu1)

    server = HTTPServer(("0.0.0.0", args.port), CoordinatorHandler)
    log.info(f"🚀 Coordenador GPU iniciado na porta {args.port}")
    log.info(f"   GPU0 (pesado): {GPU0_HOST}")
    log.info(f"   GPU1 (leve):   {GPU1_HOST}")
    log.info(f"   Routing: trading-analyst→GPU0 | qwen3:0.6b/qwen2.5:1.5b→GPU1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Coordenador encerrado.")


if __name__ == "__main__":
    main()
