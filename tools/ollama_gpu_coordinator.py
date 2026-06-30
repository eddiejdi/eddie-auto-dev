#!/usr/bin/env python3
"""Coordenador de GPUs Ollama — balanceamento de carga real com 3 endpoints.

Estratégia de roteamento (em ordem de prioridade):
  1. VRAM fit    — descarta GPUs onde o modelo não cabe
  2. Affinity    — prefere GPU onde o modelo já está carregado (evita reload)
  3. Least-load  — entre candidatos elegíveis, escolhe o com menos requisições ativas
  4. Priority    — GPU0 > GPU1 > NAS como tiebreaker de hardware

Endpoints:
  GPU0  RTX 3060 12GB  :11434  (proxy métricas :11544)
  GPU1  GTX 1050  2GB  :11435  (proxy métricas :11545)
  NAS   RTX 2060  8GB  :11436  (proxy métricas :11546)

Usage:
    python3 ollama_gpu_coordinator.py --port 11437
    systemctl restart ollama-gpu-coordinator
"""

from __future__ import annotations

import argparse
import collections
import datetime
import http.client
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [gpu-coord] %(message)s",
)
log = logging.getLogger("gpu-coord")

# ── Configuração ──────────────────────────────────────────────────────────────

DEFAULT_PORT = int(os.environ.get("GPU_COORD_PORT", "11437"))
REQUEST_TIMEOUT_SEC = int(os.environ.get("GPU_COORD_REQUEST_TIMEOUT_SEC", "240"))
POLL_INTERVAL_SEC = float(os.environ.get("GPU_COORD_POLL_INTERVAL_SEC", "10"))
HEALTH_TIMEOUT_SEC = float(os.environ.get("GPU_COORD_HEALTH_TIMEOUT_SEC", "3"))

# VRAM estimativas por padrão de nome (MB) — usado quando o modelo não está na VRAM
_VRAM_ESTIMATES: list[tuple[str, int]] = [
    ("0.5b",  400), ("0.6b",  600), ("1b",   900), ("1.5b", 1300),
    ("2b",   1800), ("3b",   2200), ("4b",   3000), ("7b",  5000),
    ("8b",   6000), ("13b", 10000), ("14b", 10500), ("32b", 22000),
    ("70b", 48000),
    # modelos nomeados
    ("trading-analyst", 6500), ("qwen3-fast", 1500), ("smollm", 600),
    ("moondream", 1700),
]

_STATS_LOCK = threading.Lock()
_TOTAL_REQUESTS = 0
_REQUEST_ERRORS = 0

# ── Ring buffer de requisições ────────────────────────────────────────────────

_PAYLOAD_LOG_CHARS = int(os.environ.get("GPU_COORD_PAYLOAD_LOG_CHARS", "500"))
_RING_SIZE = int(os.environ.get("GPU_COORD_RING_SIZE", "100"))

_ring_lock = threading.Lock()
_ring: collections.deque = collections.deque(maxlen=_RING_SIZE)

# PostgreSQL async writer — lê DATABASE_URL de /etc/default/eddie-common via EnvironmentFile
_PG_DSN = os.environ.get("GPU_COORD_PG_DSN") or os.environ.get("DATABASE_URL", "")
_pg_queue: Optional[object] = None


def _start_pg_writer() -> None:
    global _pg_queue
    try:
        import queue as _queue
        import psycopg2  # type: ignore[import]
    except ImportError:
        log.info("psycopg2 não instalado — payload log apenas em memória")
        return
    if not _PG_DSN:
        log.info("DATABASE_URL não definida — payload log apenas em memória")
        return
    _pg_queue = _queue.Queue(maxsize=500)

    def _writer() -> None:
        conn = None
        while True:
            try:
                import queue as _q
                entry = _pg_queue.get(timeout=5)  # type: ignore[union-attr]
                if conn is None or conn.closed:
                    conn = psycopg2.connect(_PG_DSN)
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS ollama_payload_log (
                                id BIGSERIAL PRIMARY KEY,
                                ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                model TEXT, endpoint TEXT, path TEXT,
                                status INT, elapsed_s FLOAT, streaming BOOLEAN,
                                prompt TEXT, response TEXT
                            )
                        """)
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO ollama_payload_log"
                        " (ts,model,endpoint,path,status,elapsed_s,streaming,prompt,response)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            entry.get("ts"), entry.get("model"), entry.get("endpoint"),
                            entry.get("path"), entry.get("status"), entry.get("elapsed_s"),
                            bool(entry.get("streaming")),
                            (entry.get("prompt") or "")[:2000],
                            (entry.get("response") or "")[:2000],
                        ),
                    )
            except Exception as exc:
                log.warning("pg_writer: %s", exc)
                conn = None

    threading.Thread(target=_writer, daemon=True, name="pg-writer").start()
    log.info("pg_writer iniciado (dsn=%s...)", _PG_DSN[:20])


def _ring_append(entry: dict) -> None:
    with _ring_lock:
        _ring.append(entry)
    if _pg_queue is not None:
        try:
            _pg_queue.put_nowait(entry)  # type: ignore[union-attr]
        except Exception:
            pass


def _ring_snapshot() -> list:
    with _ring_lock:
        return list(reversed(_ring))  # mais recente primeiro



def _clean_text(text: str, maxlen: int = _PAYLOAD_LOG_CHARS) -> str:
    """Remove <think> blocks, normaliza whitespace e trunca."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:maxlen]

def _estimate_vram_mb(model: str) -> int:
    """Estima VRAM necessária para um modelo pelo nome (MB)."""
    m = model.lower()
    for key, mb in _VRAM_ESTIMATES:
        if key in m:
            return mb
    return 4000  # conservador para desconhecidos


# ── Estado de endpoint ────────────────────────────────────────────────────────

class EndpointState:
    """Estado em tempo real de um endpoint Ollama (thread-safe)."""

    def __init__(self, name: str, host: str, vram_total_mb: int, priority: int):
        self.name = name
        self.host = host
        self.vram_total_mb = vram_total_mb
        self.priority = priority

        self._lock = threading.Lock()
        self._active: int = 0
        self._loaded: dict[str, float] = {}   # model_name → vram_mb
        self._healthy: bool = False
        self._last_poll: float = 0.0
        self._total_served: int = 0

    # ── propriedades ──────────────────────────────────────────────────────────

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def active_requests(self) -> int:
        return self._active

    @property
    def vram_used_mb(self) -> float:
        return sum(self._loaded.values())

    @property
    def vram_free_mb(self) -> float:
        return max(0.0, self.vram_total_mb - self.vram_used_mb)

    def has_model(self, model: str) -> bool:
        m = model if ":" in model else model + ":latest"
        return model in self._loaded or m in self._loaded

    # ── mutação ───────────────────────────────────────────────────────────────

    def increment(self) -> None:
        with self._lock:
            self._active += 1
            self._total_served += 1

    def decrement(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def poll(self) -> None:
        """Atualiza estado via /api/ps e /api/tags (chamado pelo poller)."""
        try:
            req = urllib.request.Request(
                f"{self.host}/api/ps",
                headers={"User-Agent": "gpu-coordinator/2.0"},
            )
            with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read())
                loaded = {}
                for m in data.get("models", []):
                    name = m.get("name", "")
                    vram = m.get("size_vram", 0) / (1024 * 1024)  # bytes → MB
                    if not vram:
                        vram = _estimate_vram_mb(name)
                    loaded[name] = vram
                with self._lock:
                    self._loaded = loaded
                    self._healthy = True
                    self._last_poll = time.monotonic()
        except Exception as exc:
            with self._lock:
                self._healthy = False
            log.warning("poll %s falhou: %s", self.name, exc)

    # ── scoring ───────────────────────────────────────────────────────────────

    def score(self, model: str) -> float:
        """Pontuação para este endpoint receber o modelo (menor = melhor).

        Retorna float('inf') se o endpoint não é elegível.
        """
        if not self._healthy:
            return float("inf")

        needed_mb = _estimate_vram_mb(model)

        # Se o modelo já está carregado, não precisa de espaço adicional
        if self.has_model(model):
            needed_mb = 0

        # VRAM insuficiente com 10% de margem de segurança
        if self.vram_free_mb < needed_mb * 1.10 and needed_mb > 0:
            return float("inf")

        score = 0.0
        # Penalidade por requisições ativas (10 pts cada)
        score += self._active * 10.0
        # Bônus por afinidade de modelo (evita reload de VRAM)
        if self.has_model(model):
            score -= 8.0
        # Penalidade de prioridade de hardware (GPU0=0, GPU1=0.5, NAS=1.0)
        score += self.priority * 0.5

        return score

    def info(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "healthy": self._healthy,
            "active_requests": self._active,
            "total_served": self._total_served,
            "vram_total_mb": self.vram_total_mb,
            "vram_used_mb": round(self.vram_used_mb, 1),
            "vram_free_mb": round(self.vram_free_mb, 1),
            "loaded_models": list(self._loaded.keys()),
        }


# ── Cluster ───────────────────────────────────────────────────────────────────

class GPUCluster:
    """Gerencia os endpoints e executa o balanceamento de carga."""

    def __init__(self, endpoints: list[EndpointState]):
        self._endpoints = endpoints
        self._poller: Optional[threading.Thread] = None

    def start_poller(self) -> None:
        """Inicia thread daemon que mantém o estado dos endpoints atualizado."""
        # Poll inicial (síncrono) para ter estado antes da 1ª requisição
        for ep in self._endpoints:
            ep.poll()
        self._evict_misplaced_models()

        def _loop() -> None:
            while True:
                time.sleep(POLL_INTERVAL_SEC)
                for ep in self._endpoints:
                    ep.poll()
                self._evict_misplaced_models()

        self._poller = threading.Thread(target=_loop, daemon=True, name="gpu-poller")
        self._poller.start()
        log.info("poller iniciado (intervalo=%.0fs, endpoints=%d)", POLL_INTERVAL_SEC, len(self._endpoints))

    def _unload_model(self, ep: EndpointState, model: str) -> None:
        """Descarrega um modelo da VRAM de um endpoint via keep_alive=0."""
        try:
            body = json.dumps({"model": model, "keep_alive": 0, "prompt": ""}).encode()
            req = urllib.request.Request(
                f"{ep.host}/api/generate",
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": "gpu-coordinator/2.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            log.info("🧹 evictado modelo %s de %s (estava na GPU errada)", model, ep.name)
        except Exception as exc:
            log.warning("falha ao evictar %s de %s: %s", model, ep.name, exc)

    def _evict_misplaced_models(self) -> None:
        """Detecta e evicta da VRAM modelos pinados carregados na GPU errada."""
        for ep in self._endpoints:
            if not ep.healthy:
                continue
            for model_name in list(ep._loaded.keys()):
                for suffix, target_ep_name in self._PIN_SUFFIX.items():
                    if model_name.endswith(suffix) and ep.name != target_ep_name:
                        log.error(
                            "🚨 modelo pinado '%s' detectado em %s (correto: %s) — evictando",
                            model_name, ep.name, target_ep_name,
                        )
                        self._unload_model(ep, model_name)

    # Modelos com sufixo ":gpuN" são pinados ao endpoint correspondente.
    # Modelos sem sufixo são roteados por potência (RTX 3060 > NAS RTX 2060 > GTX 1050).
    _PIN_SUFFIX: dict[str, str] = {
        ":gpu0": "gpu0-rtx3060",
        ":gpu1": "gpu1-gtx1050",
        ":nas":  "nas-rtx2060",
    }

    def pick(self, model: str) -> Optional[EndpointState]:
        """Retorna o melhor endpoint para o modelo. None se nenhum disponível."""
        # Pinning por sufixo — nunca vaza para outra GPU
        for suffix, ep_name in self._PIN_SUFFIX.items():
            if model.endswith(suffix):
                pinned = next((ep for ep in self._endpoints if ep.name == ep_name), None)
                if pinned and pinned.healthy:
                    log.info("roteando model=%s → %s [pinned] (active=%d vram_free=%.0fMB)",
                             model, pinned.name, pinned.active_requests, pinned.vram_free_mb)
                    return pinned
                log.warning("endpoint pinado %s indisponível para model=%s — sem fallback", ep_name, model)
                return None

        best: Optional[EndpointState] = None
        best_score = float("inf")

        for ep in self._endpoints:
            s = ep.score(model)
            log.debug("score %s model=%s → %.1f (active=%d vram_free=%.0fMB)",
                      ep.name, model, s, ep.active_requests, ep.vram_free_mb)
            if s < best_score:
                best_score = s
                best = ep

        if best is None or best_score == float("inf"):
            log.warning("nenhum endpoint elegível para model=%s", model)
            return None

        log.info("roteando model=%s → %s (score=%.1f active=%d vram_free=%.0fMB)",
                 model, best.name, best_score, best.active_requests, best.vram_free_mb)
        return best

    def health_info(self) -> dict:
        return {
            "coordinator": "ok",
            "endpoints": [ep.info() for ep in self._endpoints],
        }

    def prometheus_metrics(self) -> str:
        lines = []
        lines.append("# HELP gpu_coord_active_requests Requisições ativas por endpoint")
        lines.append("# TYPE gpu_coord_active_requests gauge")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_active_requests{{endpoint="{ep.name}",host="{ep.host}"}} {ep.active_requests}')

        lines.append("# HELP gpu_coord_vram_free_mb VRAM livre estimada por endpoint (MB)")
        lines.append("# TYPE gpu_coord_vram_free_mb gauge")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_vram_free_mb{{endpoint="{ep.name}"}} {ep.vram_free_mb:.1f}')

        lines.append("# HELP gpu_coord_healthy Endpoint saudável (1=sim, 0=não)")
        lines.append("# TYPE gpu_coord_healthy gauge")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_healthy{{endpoint="{ep.name}"}} {1 if ep.healthy else 0}')

        lines.append("# HELP gpu_coord_total_requests_served Total de requisições servidas por endpoint")
        lines.append("# TYPE gpu_coord_total_requests_served counter")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_total_requests_served{{endpoint="{ep.name}"}} {ep._total_served}')

        with _STATS_LOCK:
            total = _TOTAL_REQUESTS
            errors = _REQUEST_ERRORS
        lines.append("# HELP gpu_coord_requests_total Total de requisições recebidas pelo coordinator")
        lines.append("# TYPE gpu_coord_requests_total counter")
        lines.append(f"gpu_coord_requests_total {total}")
        lines.append("# HELP gpu_coord_request_errors_total Total de requisições com erro")
        lines.append("# TYPE gpu_coord_request_errors_total counter")
        lines.append(f"gpu_coord_request_errors_total {errors}")

        return "\n".join(lines) + "\n"


# ── HTTP handler ──────────────────────────────────────────────────────────────

_cluster: Optional[GPUCluster] = None


class CoordinatorHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args) -> None:
        pass  # silencia log padrão

    # ── leitura ───────────────────────────────────────────────────────────────

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _extract_model(self, body: bytes) -> str:
        try:
            return json.loads(body).get("model", "") or ""
        except Exception:
            return ""

    # ── escrita ───────────────────────────────────────────────────────────────

    def _json_response(self, status: int, data: dict | str) -> None:
        body = (json.dumps(data, indent=2) if isinstance(data, dict) else data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _text_response(self, status: int, text: str, content_type: str = "text/plain") -> None:
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── proxy ─────────────────────────────────────────────────────────────────

    def _forward(self, ep: EndpointState, method: str, path: str, body: bytes,
                 streaming: bool) -> None:
        """Encaminha a requisição para o endpoint escolhido."""
        parsed = urllib.parse.urlparse(ep.host)
        host = parsed.hostname
        port = parsed.port or 80

        # Extrai prompt para o ring buffer
        prompt_preview = ""
        model_name = ""
        try:
            req_data = json.loads(body) if body else {}
            model_name = req_data.get("model", "")
            raw_prompt = req_data.get("prompt") or ""
            if not raw_prompt:
                msgs = req_data.get("messages", [])
                raw_prompt = " | ".join(m.get("content", "")[:200] for m in msgs[-3:])
            prompt_preview = _clean_text(raw_prompt)
        except Exception:
            pass

        ep.increment()
        t_start = time.monotonic()
        with _STATS_LOCK:
            global _TOTAL_REQUESTS
            _TOTAL_REQUESTS += 1
        try:
            conn = http.client.HTTPConnection(host, port, timeout=REQUEST_TIMEOUT_SEC)
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "gpu-coordinator/2.0",
                "X-Routed-By": "gpu-coord",
                "X-GPU-Endpoint": ep.name,
            }
            if body:
                headers["Content-Length"] = str(len(body))

            conn.request(method, path, body=body or None, headers=headers)
            resp = conn.getresponse()

            resp_preview = ""
            if streaming:
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.getheader("Content-Type", "application/json"))
                self.send_header("X-GPU-Endpoint", ep.name)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                chunks = []
                try:
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        chunks.append(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                try:
                    full = b"".join(chunks).decode(errors="replace")
                    # streaming: cada linha é JSON com "response" parcial
                    tokens = [json.loads(ln).get("response", "") for ln in full.splitlines() if ln.strip()]
                    resp_preview = _clean_text("".join(tokens))
                except Exception:
                    pass
            else:
                resp_body = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.getheader("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(resp_body)))
                self.send_header("X-GPU-Endpoint", ep.name)
                self.end_headers()
                try:
                    self.wfile.write(resp_body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                try:
                    resp_preview = _clean_text(json.loads(resp_body).get("response", ""))
                except Exception:
                    resp_preview = resp_body[:_PAYLOAD_LOG_CHARS].decode(errors="replace")

            elapsed = round(time.monotonic() - t_start, 2)

            _ring_append({
                "ts":       datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "model":    model_name,
                "endpoint": ep.name,
                "path":     path,
                "status":   resp.status,
                "elapsed_s": elapsed,
                "prompt":   prompt_preview,
                "response": resp_preview,
                "streaming": streaming,
            })
            log.info("✅ %s model=%s → %s status=%d elapsed=%.1fs",
                     path, model_name, ep.name, resp.status, elapsed)

            if resp.status >= 400:
                with _STATS_LOCK:
                    global _REQUEST_ERRORS
                    _REQUEST_ERRORS += 1

        except Exception as exc:
            elapsed = round(time.monotonic() - t_start, 2)
            log.warning("forward para %s falhou: %s", ep.name, exc)
            _ring_append({
                "ts":       datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "model":    model_name,
                "endpoint": ep.name,
                "path":     path,
                "status":   503,
                "elapsed_s": elapsed,
                "prompt":   prompt_preview,
                "response": "",
                "error":    str(exc),
                "streaming": streaming,
            })
            with _STATS_LOCK:
                _REQUEST_ERRORS += 1
            self._json_response(503, {"error": str(exc), "endpoint": ep.name})
        finally:
            ep.decrement()
            try:
                conn.close()
            except Exception:
                pass

    def _route_and_forward(self) -> None:
        """Lê body, escolhe GPU, encaminha."""
        body = self._read_body()
        model = self._extract_model(body)

        # Detecta se cliente quer streaming
        streaming = False
        try:
            streaming = json.loads(body).get("stream", True)
        except Exception:
            pass

        ep = _cluster.pick(model) if _cluster else None
        if ep is None:
            self._json_response(503, {"error": "nenhum GPU disponível para model=" + model})
            return

        self._forward(ep, "POST", self.path, body, streaming)

    def _passthrough_get(self, host: str) -> None:
        """GET simples passado para um host fixo."""
        try:
            req = urllib.request.Request(
                f"{host}{self.path}",
                headers={"User-Agent": "gpu-coordinator/2.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read()
                ct = resp.headers.get("Content-Type", "application/json")
                self._text_response(200, body.decode(errors="replace"), ct)
        except Exception as exc:
            self._json_response(503, {"error": str(exc)})

    def _handle_ps(self) -> None:
        """Agrega /api/ps de todos os endpoints."""
        models: list = []
        for ep in (_cluster._endpoints if _cluster else []):
            if not ep.healthy:
                continue
            try:
                req = urllib.request.Request(
                    f"{ep.host}/api/ps",
                    headers={"User-Agent": "gpu-coordinator/2.0"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read())
                    for m in data.get("models", []):
                        m["_endpoint"] = ep.name
                        models.append(m)
            except Exception:
                pass
        self._json_response(200, {"models": models})

    def _handle_tags(self) -> None:
        """Agrega /api/tags de todos os endpoints (sem duplicatas)."""
        seen: set[str] = set()
        models: list = []
        for ep in (_cluster._endpoints if _cluster else []):
            if not ep.healthy:
                continue
            try:
                req = urllib.request.Request(
                    f"{ep.host}/api/tags",
                    headers={"User-Agent": "gpu-coordinator/2.0"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read())
                    for m in data.get("models", []):
                        if m["name"] not in seen:
                            seen.add(m["name"])
                            models.append(m)
            except Exception:
                pass
        self._json_response(200, {"models": models})

    # ── do_GET / do_POST ──────────────────────────────────────────────────────

    def do_GET(self) -> None:
        if self.path == "/api/ps":
            self._handle_ps()
        elif self.path.startswith("/api/tags"):
            self._handle_tags()
        elif self.path == "/health":
            self._json_response(200, _cluster.health_info() if _cluster else {"error": "not initialized"})
        elif self.path == "/metrics":
            self._text_response(200, _cluster.prometheus_metrics() if _cluster else "", "text/plain; version=0.0.4")
        elif self.path.startswith("/api/requests"):
            # Ring buffer das últimas requisições com preview de prompt/resposta
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            limit = int(params.get("limit", ["50"])[0])
            entries = _ring_snapshot()[:limit]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            body = json.dumps({"requests": entries, "total": len(_ring_snapshot())}).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            # fallback: primeiro endpoint saudável
            ep = next((e for e in (_cluster._endpoints if _cluster else []) if e.healthy), None)
            if ep:
                self._passthrough_get(ep.host)
            else:
                self._json_response(503, {"error": "no healthy endpoint"})

    def do_POST(self) -> None:
        if self.path in ("/api/generate", "/api/chat", "/api/embed", "/api/embeddings"):
            self._route_and_forward()
        else:
            # pull, push, etc. → GPU0 (primeiro endpoint)
            ep = _cluster._endpoints[0] if _cluster and _cluster._endpoints else None
            if ep:
                body = self._read_body()
                self._forward(ep, "POST", self.path, body, streaming=False)
            else:
                self._json_response(503, {"error": "no endpoints configured"})


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global _cluster

    parser = argparse.ArgumentParser(description="Coordenador de GPUs Ollama v2")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--gpu0", default=os.environ.get("OLLAMA_GPU0_HOST", "http://192.168.15.2:11434"))
    parser.add_argument("--gpu1", default=os.environ.get("OLLAMA_GPU1_HOST", "http://192.168.15.2:11435"))
    parser.add_argument("--nas",  default=os.environ.get("OLLAMA_NAS_HOST",  "http://192.168.15.4:11436"))
    args = parser.parse_args()

    endpoints = [
        EndpointState("gpu0-rtx3060", args.gpu0, vram_total_mb=12 * 1024, priority=0),  # ~170 GFLOPS FP32
        EndpointState("nas-rtx2060",  args.nas,  vram_total_mb=8 * 1024,  priority=1),  # ~57 GFLOPS FP32
        EndpointState("gpu1-gtx1050", args.gpu1, vram_total_mb=2 * 1024,  priority=2),  # ~19 GFLOPS FP32
    ]

    _cluster = GPUCluster(endpoints)
    _cluster.start_poller()
    _start_pg_writer()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), CoordinatorHandler)
    server.daemon_threads = True

    log.info("🚀 GPU Coordinator v2 iniciado na porta %d", args.port)
    for ep in endpoints:
        log.info("   %s  %s  %dGB  healthy=%s  modelos=%s",
                 ep.name, ep.host, ep.vram_total_mb // 1024, ep.healthy,
                 list(ep._loaded.keys()))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Coordenador encerrado.")


if __name__ == "__main__":
    main()
