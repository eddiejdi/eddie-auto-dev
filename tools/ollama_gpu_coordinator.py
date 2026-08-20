#!/usr/bin/env python3
"""Coordenador de GPUs Ollama — balanceamento de carga real com 3 endpoints.

Estratégia de roteamento (em ordem de prioridade):
  1. Soft-pin    — sufixo :gpu0/:gpu1/:nas prefere o endpoint, mas faz spill
                   se ocupado/indisponível (distribui carga entre todas as GPUs)
  2. VRAM fit    — descarta GPUs onde o modelo não cabe
  3. Affinity    — prefere GPU onde o modelo já está carregado (evita reload)
  4. Least-load  — entre candidatos elegíveis, escolhe o com menos requisições ativas
  5. Priority    — GPU0 > NAS > GPU1 como tiebreaker de hardware

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
import queue
import re
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
# Evicta modelo ocioso se VRAM livre cair abaixo deste valor (MB)
EVICT_THRESHOLD_MB = int(os.environ.get("GPU_COORD_EVICT_THRESHOLD_MB", "2048"))
# Falhas consecutivas de poll antes de marcar endpoint como unhealthy
FAIL_THRESHOLD = int(os.environ.get("GPU_COORD_FAIL_THRESHOLD", "2"))
# ── RAM do host (endpoints com exporter dedicado, ex. NAS) ──────────────────
# VRAM não é o gargalo em endpoints como a NAS (RTX 2060 8GB, com sobra) — RAM
# do sistema é (8GB total, sem swap). Ollama só evicta por pressão de VRAM,
# nunca por RAM do host, então o coordenador cobre essa lacuna consultando um
# exporter dedicado (netdata da NAS só escuta em 127.0.0.1, inacessível daqui).
# Ver docs/variables-taxonomy/NAS_RAM_EXPORTER.md.
NAS_RAM_EXPORTER_HOST = os.environ.get(
    "OLLAMA_NAS_RAM_EXPORTER_HOST", "http://192.168.15.4:11447"
)
RAM_SAFETY_MARGIN_MB = int(os.environ.get("GPU_COORD_NAS_RAM_MARGIN_MB", "400"))
RAM_OVERHEAD_PER_MODEL_MB = int(os.environ.get("GPU_COORD_NAS_RAM_MODEL_OVERHEAD_MB", "500"))
RAM_EVICT_THRESHOLD_MB = int(os.environ.get("GPU_COORD_NAS_MIN_FREE_RAM_MB", "900"))
# Poll bem-sucedido mais antigo que isso ⇒ estado stale ⇒ endpoint não-elegível
STALE_AFTER_SEC = float(os.environ.get(
    "GPU_COORD_STALE_AFTER_SEC", str(max(POLL_INTERVAL_SEC * 3, 30.0))
))
# Cap de acúmulo de chunks de streaming para preview (bytes)
STREAM_PREVIEW_CAP = int(os.environ.get("GPU_COORD_STREAM_PREVIEW_CAP", str(256 * 1024)))
# ── Trading: intocável; VRAM livre da NAS liberada só a auxiliares pequenos ──
# Política (2026-07):
#   1. Modelos trading-* NUNCA são evictados.
#   2. Com trading residente na NAS, só cabem modelos AUXILIARES PEQUENOS
#      na VRAM livre (sem despejar o analyst). Modelos grandes (≥7B etc.)
#      vão para GPU1/NAS.
#   3. Nunca se abre espaço na NAS evictando trading para caber auxiliar.
#
# Default cobre: trading-analyst, trading-analyst-phi4, candidates, sentiment…
PROTECTED_MODELS = tuple(
    p.strip() for p in os.environ.get(
        "GPU_COORD_PROTECTED_MODELS",
        "trading-analyst,trading-sentiment,trading-",
    ).split(",") if p.strip()
)
# Reserva "inteligente" da NAS: trading prioritário + auxiliares pequenos no resto.
TRADING_RESERVE_GPU0 = os.environ.get(
    "GPU_COORD_TRADING_RESERVE_GPU0", "1"
).strip().lower() not in {"0", "false", "no", "off"}
TRADING_GPU0_NAME = os.environ.get("GPU_COORD_TRADING_GPU0_NAME", "nas-rtx2060")
# Exclusivo: NÃO rotear agenda/aux para a NAS (evita timeout do trading-analyst).
# 2026-07-30: soft-pin spill da agenda enchia a GPU0 e o trading dava connect timeout.
# GPU_COORD_TRADING_EXCLUSIVE_GPU0=0 reativa auxiliares pequenos na VRAM livre.
TRADING_EXCLUSIVE_GPU0 = os.environ.get(
    "GPU_COORD_TRADING_EXCLUSIVE_GPU0", "1"
).strip().lower() not in {"0", "false", "no", "off"}
# Teto de VRAM estimada para auxiliar ao lado do trading (~1–2B).
# gemma3:1b / lfm2.5 / llama3.2:1b cabem; mistral:7b / llama3.1:8b não.
AUX_MAX_VRAM_MB = max(
    256, int(os.environ.get("GPU_COORD_AUX_MAX_VRAM_MB", "1800"))
)
# Margem de VRAM livre que deve sobrar após carregar o auxiliar (MB).
# Evita espremer o trading / fragmentar a NAS.
TRADING_HEADROOM_MB = max(
    0, int(os.environ.get("GPU_COORD_TRADING_HEADROOM_MB", "1024"))
)

# Soft-pin: sufixo :gpuN é preferência, não prisão. Se o endpoint pinado está
# ocupado (active >= threshold) ou unhealthy, o least-load escolhe outra GPU
# que POSUA o mesmo modelo — spill para GPU0 só se couber como auxiliar pequeno.
SOFT_PIN = os.environ.get("GPU_COORD_SOFT_PIN", "1").strip().lower() not in {
    "0", "false", "no", "off",
}
SOFT_PIN_BUSY_THRESHOLD = max(
    1, int(os.environ.get("GPU_COORD_SOFT_PIN_BUSY", "1"))
)
# Status HTTP do backend tratados como "ocupado/retriável" (failover p/ outra GPU).
# GPU1 (NUM_PARALLEL=1) devolve 503 "maximum pending requests exceeded".
_RETRIABLE_BACKEND_STATUS = frozenset({429, 502, 503, 504})


def is_protected_model(name: str) -> bool:
    """True se o modelo é da família protegida (trading e afins)."""
    if not name:
        return False
    n = name.strip()
    for prefix in PROTECTED_MODELS:
        if n.startswith(prefix) or n.split(":")[0].startswith(prefix.rstrip(":")):
            return True
    return False


def is_trading_request(model: str) -> bool:
    """Tráfego de trading: sempre elegível na GPU0; prioridade máxima."""
    return is_protected_model(model)


def is_small_auxiliary_model(model: str, *, max_vram_mb: int | None = None) -> bool:
    """True se o modelo é pequeno o bastante para coexistir com trading na 3060.

    Usa estimativa de VRAM pelo nome (mesma tabela do fit). Nunca classifica
    a família trading como “auxiliar”.
    """
    if not model or is_trading_request(model):
        return False
    cap = int(max_vram_mb if max_vram_mb is not None else AUX_MAX_VRAM_MB)
    return _estimate_vram_mb(model) <= cap

# VRAM estimativas por padrão de nome (MB) — usado quando o modelo não está na VRAM
_VRAM_ESTIMATES: list[tuple[str, int]] = [
    ("0.5b",  400), ("0.6b",  600), ("1b",   900), ("1.5b", 1300),
    ("2b",   1800), ("3b",   2200), ("4b",   3000), ("7b",  5000),
    ("8b",   6000), ("13b", 10000), ("14b", 10500), ("32b", 22000),
    ("70b", 48000),
    # modelos nomeados
    ("trading-analyst", 6500), ("gemma3", 1000), ("smollm", 600),
    ("moondream", 1700), ("lfm2.5-vl", 500), ("lfm2", 1100), ("lfm", 1100),
    # aliases canônicos de visão (vision-*)
    ("vision-moondream", 1700), ("vision-vl", 500), ("vision-gemma3", 1000),
    ("vision", 1700),
    ("phi4-mini", 2500), ("phi3", 2200), ("llama3.2", 900),
    # GPU1 GGUF quant (Q4_0 / IQ3) — pesos ~0.7–0.9GB + KV
    ("lfm2.5", 900), ("smollm2", 900), ("smollm", 800),
    # personas Eddie / shared (~llama3.1 8B Q4_K_M) — medido na NAS RTX 2060: ~7535MB
    ("eddie-persona", 7600), ("shared-homelab", 7600),
    ("shared-assistant", 7600), ("shared-coder", 7600),
    ("shared-whatsapp", 7600), ("persona", 7600),
]

_STATS_LOCK = threading.Lock()
_TOTAL_REQUESTS = 0
_REQUEST_ERRORS = 0

# ── Histogram de latência por modelo ─────────────────────────────────────────

_DURATION_BUCKETS = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 240.0, float("inf")]
_dur_lock = threading.Lock()
# model → {le: count}
_dur_buckets: dict[str, dict[float, int]] = {}
_dur_sum: dict[str, float] = {}
_dur_count: dict[str, int] = {}


def _record_duration(model: str, elapsed_s: float) -> None:
    with _dur_lock:
        if model not in _dur_buckets:
            _dur_buckets[model] = {le: 0 for le in _DURATION_BUCKETS}
            _dur_sum[model] = 0.0
            _dur_count[model] = 0
        for le in _DURATION_BUCKETS:
            if elapsed_s <= le:
                _dur_buckets[model][le] += 1
        _dur_sum[model] += elapsed_s
        _dur_count[model] += 1

# ── Ring buffer de requisições ────────────────────────────────────────────────

# Auditoria: por padrão guarda prompt/resposta quase inteiros (32k chars).
# Override via GPU_COORD_PAYLOAD_LOG_CHARS se precisar reduzir memória.
_PAYLOAD_LOG_CHARS = int(os.environ.get("GPU_COORD_PAYLOAD_LOG_CHARS", "32000"))
_RING_SIZE = int(os.environ.get("GPU_COORD_RING_SIZE", "500"))
_PG_PROMPT_CHARS = int(os.environ.get("GPU_COORD_PG_PROMPT_CHARS", str(_PAYLOAD_LOG_CHARS)))

_ring_lock = threading.Lock()
_ring: collections.deque = collections.deque(maxlen=_RING_SIZE)

# PostgreSQL async writer — lê DATABASE_URL de /etc/default/eddie-common via EnvironmentFile
_PG_DSN = os.environ.get("GPU_COORD_PG_DSN") or os.environ.get("DATABASE_URL", "")
_pg_queue: object | None = None


def _start_pg_writer() -> None:
    global _pg_queue
    try:
        import psycopg2  # type: ignore[import]
    except ImportError:
        log.info("psycopg2 não instalado — payload log apenas em memória")
        return
    if not _PG_DSN:
        log.info("DATABASE_URL não definida — payload log apenas em memória")
        return
    _pg_queue = queue.Queue(maxsize=500)

    def _writer() -> None:
        conn = None
        while True:
            try:
                entry = _pg_queue.get(timeout=5)  # type: ignore[union-attr]
            except queue.Empty:
                continue
            try:
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
                            (entry.get("prompt") or "")[:_PG_PROMPT_CHARS],
                            (entry.get("response") or "")[:_PG_PROMPT_CHARS],
                        ),
                    )
            except Exception as exc:
                log.warning("pg_writer: %s", exc)
                try:
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass
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

    def __init__(self, name: str, host: str, vram_total_mb: int, priority: int,
                 ram_exporter_host: str | None = None):
        self.name = name
        self.host = host
        self.vram_total_mb = vram_total_mb
        self.priority = priority
        # Só configurado para endpoints cujo gargalo real é RAM do host, não
        # VRAM (hoje só a NAS) — ver RAM_SAFETY_MARGIN_MB acima.
        self.ram_exporter_host = ram_exporter_host

        self._lock = threading.Lock()
        self._active: int = 0
        self._loaded: dict[str, float] = {}        # model_name → vram_mb (residente, /api/ps)
        self._available: set[str] = set()          # modelos que o endpoint POSSUI (/api/tags)
        self._available_known: bool = False        # False = catálogo desconhecido → fail-open
        self._model_active: dict[str, int] = {}    # model_name → requests ativas
        self._model_last_used: dict[str, float] = {}  # model_name → monotonic timestamp
        self._healthy: bool = False
        self._last_poll: float = 0.0
        self._last_ok_poll: float = 0.0
        self._consec_fails: int = 0
        self._total_served: int = 0
        self._ram_total_mb: float = 0.0
        # None = desconhecido (exporter nunca respondeu) → fail-open, não bloqueia roteamento
        self._ram_available_mb: float | None = None

    # ── propriedades ──────────────────────────────────────────────────────────

    @property
    def healthy(self) -> bool:
        # Estado stale (poller morto/travado) invalida o healthy=True antigo
        if self._healthy and time.monotonic() - self._last_ok_poll > STALE_AFTER_SEC:
            return False
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
        """O modelo está carregado em VRAM agora? (afinidade — evita reload)"""
        m = model if ":" in model else model + ":latest"
        return model in self._loaded or m in self._loaded

    def has_model_available(self, model: str) -> bool:
        """O endpoint POSSUI este modelo? (elegibilidade — evita 404)

        Fail-open deliberado: enquanto o catálogo for desconhecido (endpoint
        novo, /api/tags falhando), retorna True para não bloquear roteamento
        que hoje funciona. Só filtra com conhecimento positivo da ausência.
        """
        with self._lock:
            if not self._available_known:
                return True
            avail = self._available
            loaded = set(self._loaded)
        m = model if ":" in model else model + ":latest"
        # Um modelo residente está, por definição, disponível.
        return bool({model, m} & (avail | loaded))

    # ── mutação ───────────────────────────────────────────────────────────────

    def increment(self, model: str = "") -> None:
        with self._lock:
            self._active += 1
            self._total_served += 1
            if model:
                self._model_active[model] = self._model_active.get(model, 0) + 1

    def decrement(self, model: str = "") -> None:
        with self._lock:
            self._active = max(0, self._active - 1)
            if model:
                self._model_active[model] = max(0, self._model_active.get(model, 0) - 1)
                self._model_last_used[model] = time.monotonic()

    def has_protected_resident(self) -> bool:
        """Há modelo protegido (trading) residente em VRAM neste endpoint?"""
        with self._lock:
            return any(is_protected_model(n) for n in self._loaded)

    def evictable_models(self) -> list[tuple[float, str]]:
        """Retorna (vram_mb, name) ociosos, não-pinados e NÃO protegidos.

        Trading (e demais PROTECTED_MODELS) é intocável — nunca entra na lista.
        """
        with self._lock:
            result = []
            for name, vram in self._loaded.items():
                if self._model_active.get(name, 0) > 0:
                    continue
                if any(name.endswith(s) for s in (":gpu0", ":gpu1", ":nas")):
                    continue
                if is_protected_model(name):
                    continue
                result.append((vram, name))
        return sorted(result, reverse=True)

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
                    if not self._healthy:
                        log.info("endpoint %s recuperado (healthy)", self.name)
                    self._healthy = True
                    self._consec_fails = 0
                    now = time.monotonic()
                    self._last_poll = now
                    self._last_ok_poll = now
        except Exception as exc:
            with self._lock:
                self._consec_fails += 1
                self._last_poll = time.monotonic()
                if self._consec_fails >= FAIL_THRESHOLD and self._healthy:
                    self._healthy = False
                    log.warning("endpoint %s marcado unhealthy após %d falhas de poll",
                                self.name, self._consec_fails)
            log.warning("poll %s falhou (%d/%d): %s",
                        self.name, self._consec_fails, FAIL_THRESHOLD, exc)

        if self._healthy:
            self._poll_tags()
            self.poll_ram()

    def poll_ram(self) -> None:
        """Atualiza RAM disponível do host via exporter dedicado (só NAS hoje).

        Falha aqui não derruba o endpoint (fail-open) — só deixa a checagem de
        RAM pausada (valor anterior preservado) até o próximo poll bem-sucedido.
        """
        if not self.ram_exporter_host:
            return
        try:
            req = urllib.request.Request(
                f"{self.ram_exporter_host}/ram",
                headers={"User-Agent": "gpu-coordinator/2.0"},
            )
            with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read())
            with self._lock:
                self._ram_total_mb = float(data.get("mem_total_mb") or 0.0)
                self._ram_available_mb = float(data.get("mem_available_mb") or 0.0)
        except Exception as exc:
            log.debug("poll_ram %s falhou (checagem de RAM pausada): %s", self.name, exc)

    def _poll_tags(self) -> None:
        """Atualiza o catálogo de modelos que o endpoint possui (/api/tags).

        Falha aqui NÃO marca o endpoint unhealthy nem invalida o catálogo
        anterior: um /api/tags intermitente não pode tirar uma GPU do pool.
        """
        try:
            req = urllib.request.Request(
                f"{self.host}/api/tags",
                headers={"User-Agent": "gpu-coordinator/2.0"},
            )
            with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read())
            names = {m.get("name", "") for m in data.get("models", [])}
            names.discard("")
            if not names:
                return  # resposta vazia/inesperada — preserva o catálogo anterior
            with self._lock:
                if names != self._available:
                    log.info("catálogo de %s atualizado: %d modelos", self.name, len(names))
                self._available = names
                self._available_known = True
        except Exception as exc:
            log.debug("tags %s falhou (catálogo anterior preservado): %s", self.name, exc)

    def mark_unhealthy(self, reason: str = "") -> None:
        """Marca imediatamente como unhealthy (ex.: falha de conexão no forward)."""
        with self._lock:
            if self._healthy:
                log.warning("endpoint %s marcado unhealthy: %s", self.name, reason or "forward falhou")
            self._healthy = False
            self._consec_fails = max(self._consec_fails, FAIL_THRESHOLD)

    # ── scoring ───────────────────────────────────────────────────────────────

    def score(self, model: str) -> float:
        """Pontuação para este endpoint receber o modelo (menor = melhor).

        Retorna float('inf') se o endpoint não é elegível.
        """
        if not self.healthy:
            return float("inf")

        # Endpoint não possui o modelo — encaminhar para cá devolve 404.
        # Era a causa de 116 requisições de trading-analyst perdidas em 2 dias
        # (roteadas para a NAS, que não tem esse modelo).
        if not self.has_model_available(model):
            return float("inf")

        needed_mb = _estimate_vram_mb(model)

        # Se o modelo já está carregado, não precisa de espaço adicional
        if self.has_model(model):
            needed_mb = 0

        trading_here = (
            TRADING_RESERVE_GPU0
            and self.name == TRADING_GPU0_NAME
            and self.has_protected_resident()
        )
        # GPU0 exclusiva do trading: agenda/soft-pin NUNCA compete com o analyst.
        if (
            TRADING_RESERVE_GPU0
            and TRADING_EXCLUSIVE_GPU0
            and self.name == TRADING_GPU0_NAME
            and not is_trading_request(model)
        ):
            return float("inf")

        if trading_here and not is_trading_request(model):
            # Auxiliar pequeno na VRAM livre da 3060 — só se EXCLUSIVE=0.
            if not is_small_auxiliary_model(model):
                return float("inf")
            if needed_mb > 0:
                min_free = needed_mb * 1.10 + float(TRADING_HEADROOM_MB)
                if self.vram_free_mb < min_free:
                    return float("inf")

        # VRAM insuficiente com 10% de margem de segurança (caso geral)
        if self.vram_free_mb < needed_mb * 1.10 and needed_mb > 0:
            return float("inf")

        # RAM do host (só endpoints com exporter dedicado — hoje só a NAS).
        # Modelo já residente não precisa de RAM extra (sem novo runner).
        if self.ram_exporter_host and self._ram_available_mb is not None:
            ram_needed_mb = 0 if self.has_model(model) else RAM_OVERHEAD_PER_MODEL_MB
            if self._ram_available_mb < ram_needed_mb + RAM_SAFETY_MARGIN_MB:
                return float("inf")

        score = 0.0
        # Penalidade por requisições ativas (peso alto → least-load real entre GPUs)
        score += self._active * 12.0
        # Bônus por afinidade de modelo (evita reload de VRAM)
        if self.has_model(model):
            score -= 8.0
        # Tráfego de trading: forte preferência pela GPU0 (casa do analyst)
        if is_trading_request(model) and self.name == TRADING_GPU0_NAME:
            score -= 20.0
        # Trading em GPU0 ocupada: ainda assim preferir GPU0 (não ir para NAS)
        if is_trading_request(model) and self.name == TRADING_GPU0_NAME:
            score -= min(self._active, 5) * 3.0  # anula parte da pena de active
        # Auxiliar na 3060 com trading: elegível, mas ligeiramente menos preferido
        # que GPU1/NAS ociosas (evita saturar a casa do trading sem necessidade).
        if trading_here and not is_trading_request(model):
            score += 4.0
        # Penalidade leve de prioridade de hardware (GPU0=0, NAS=0.5, GPU1=1.0)
        # Mantida baixa para que endpoint livre em hardware "pior" vença um ocupado.
        score += self.priority * 0.5
        # Pequena preferência por quem já atendeu menos (espalha carga no longo prazo)
        score += min(self._total_served, 50) * 0.02

        return score

    def info(self) -> dict:
        d = {
            "name": self.name,
            "host": self.host,
            "healthy": self.healthy,
            "consecutive_poll_failures": self._consec_fails,
            "active_requests": self._active,
            "total_served": self._total_served,
            "vram_total_mb": self.vram_total_mb,
            "vram_used_mb": round(self.vram_used_mb, 1),
            "vram_free_mb": round(self.vram_free_mb, 1),
            "loaded_models": list(self._loaded.keys()),
            "available_models_known": self._available_known,
            "available_models_count": len(self._available),
        }
        if self.ram_exporter_host:
            d["ram_total_mb"] = round(self._ram_total_mb, 1)
            d["ram_available_mb"] = (
                round(self._ram_available_mb, 1) if self._ram_available_mb is not None else None
            )
        return d


# ── Cluster ───────────────────────────────────────────────────────────────────

class GPUCluster:
    """Gerencia os endpoints e executa o balanceamento de carga."""

    def __init__(self, endpoints: list[EndpointState]):
        self._endpoints = endpoints
        self._poller: threading.Thread | None = None
        self._stop = threading.Event()

    def _poll_all(self) -> None:
        """Poll paralelo — um endpoint travado não atrasa os demais."""
        threads = [
            threading.Thread(target=ep.poll, daemon=True, name=f"poll-{ep.name}")
            for ep in self._endpoints
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=HEALTH_TIMEOUT_SEC + 2)

    def start_poller(self) -> None:
        """Inicia thread daemon que mantém o estado dos endpoints atualizado."""
        # Poll inicial (síncrono) para ter estado antes da 1ª requisição
        self._poll_all()
        try:
            self._evict_misplaced_models()
        except Exception:
            log.exception("eviction inicial falhou")

        def _loop() -> None:
            while not self._stop.is_set():
                self._stop.wait(POLL_INTERVAL_SEC)
                if self._stop.is_set():
                    break
                # Nenhuma exceção pode matar o poller — estado stale é pior que ciclo perdido
                try:
                    self._poll_all()
                    self._evict_misplaced_models()
                    self._evict_under_pressure()
                except Exception:
                    log.exception("ciclo do poller falhou — tentando novamente no próximo intervalo")

        self._poller = threading.Thread(target=_loop, daemon=True, name="gpu-poller")
        self._poller.start()
        log.info("poller iniciado (intervalo=%.0fs, endpoints=%d)", POLL_INTERVAL_SEC, len(self._endpoints))

    def stop(self) -> None:
        self._stop.set()

    def _unload_model(self, ep: EndpointState, model: str) -> None:
        """Descarrega um modelo da VRAM de um endpoint via keep_alive=0.

        Nunca descarrega família trading / PROTECTED_MODELS.
        """
        if is_protected_model(model):
            log.error(
                "🚫 recusado evict de modelo protegido %s em %s (trading intocável)",
                model,
                ep.name,
            )
            return
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
            log.info("🧹 evictado modelo %s de %s", model, ep.name)
        except Exception as exc:
            log.warning("falha ao evictar %s de %s: %s", model, ep.name, exc)

    def _evict_for_space(self, ep: EndpointState, needed_mb: float) -> bool:
        """Evicta modelos ociosos de ep até needed_mb caber. Retorna True se liberou espaço.

        Na GPU0 com trading residente, NÃO tenta abrir espaço por eviction
        (trading é intocável; auxiliares só usam VRAM já livre).
        """
        if (
            TRADING_RESERVE_GPU0
            and ep.name == TRADING_GPU0_NAME
            and ep.has_protected_resident()
        ):
            log.debug(
                "skip eviction-for-space em %s com trading residente (needed=%.0fMB free=%.0fMB)",
                ep.name,
                needed_mb,
                ep.vram_free_mb,
            )
            return False
        freed = False
        for vram, model in ep.evictable_models():
            if ep.vram_free_mb >= needed_mb * 1.10:
                break
            log.info("💾 evictando %s de %s para abrir espaço (livre=%.0fMB, necessário=%.0fMB)",
                     model, ep.name, ep.vram_free_mb, needed_mb)
            self._unload_model(ep, model)
            with ep._lock:
                ep._loaded.pop(model, None)
            freed = True
        return freed

    def _evict_under_pressure(self) -> None:
        """Evicta proativamente o maior modelo ocioso sob pressão de VRAM ou,
        em endpoints com exporter dedicado (ex. NAS), de RAM do host."""
        for ep in self._endpoints:
            if not ep.healthy:
                continue
            vram_pressure = ep.vram_free_mb < EVICT_THRESHOLD_MB
            ram_pressure = (
                ep.ram_exporter_host is not None
                and ep._ram_available_mb is not None
                and ep._ram_available_mb < RAM_EVICT_THRESHOLD_MB
            )
            if not (vram_pressure or ram_pressure):
                continue
            evictable = ep.evictable_models()
            if not evictable:
                continue
            vram, model = evictable[0]
            if vram_pressure:
                log.info("⚡ pressão VRAM %s (livre=%.0fMB < %dMB) — evictando %s (%.0fMB)",
                         ep.name, ep.vram_free_mb, EVICT_THRESHOLD_MB, model, vram)
            else:
                log.info("⚡ pressão RAM %s (livre=%.0fMB < %dMB) — evictando %s (%.0fMB VRAM)",
                         ep.name, ep._ram_available_mb, RAM_EVICT_THRESHOLD_MB, model, vram)
            self._unload_model(ep, model)
            with ep._lock:
                ep._loaded.pop(model, None)

    def _ensure_ram_headroom(self, ep: EndpointState, model: str) -> None:
        """Libera RAM do host evictando modelos ociosos até haver folga para `model`.

        Só atua em endpoints com ram_exporter_host configurado (hoje só a NAS,
        cujo gargalo real é RAM sem swap — VRAM sobra). Chamado no caminho de
        soft-pin, que ignora score()/VRAM e roteia direto para o endpoint
        pinado — sem isso, um modelo novo (:nas) poderia estourar a RAM do
        host antes do próximo poll. Best-effort: exporter fora do ar não
        bloqueia o roteamento (fail-open).
        """
        if not ep.ram_exporter_host or ep.has_model(model):
            return
        needed = RAM_OVERHEAD_PER_MODEL_MB + RAM_SAFETY_MARGIN_MB
        if ep._ram_available_mb is None or ep._ram_available_mb >= needed:
            return
        for _, name in ep.evictable_models():
            if ep._ram_available_mb is not None and ep._ram_available_mb >= needed:
                break
            log.info("💾 RAM baixa em %s (%.0fMB < %.0fMB) — evictando %s antes de rotear %s",
                     ep.name, ep._ram_available_mb or 0.0, needed, name, model)
            self._unload_model(ep, name)
            with ep._lock:
                ep._loaded.pop(name, None)
            time.sleep(1.5)  # dá tempo do runner encerrar antes de reconsultar RAM
            ep.poll_ram()

    def _evict_misplaced_models(self) -> None:
        """Detecta e evicta da VRAM modelos pinados carregados na GPU errada.

        Com SOFT_PIN ativo o spill intencional carrega :gpu1 na GPU0/NAS —
        NÃO descarrega nesses casos (senão mata o request no meio da geração).
        """
        if SOFT_PIN:
            return
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

    def _least_load_pick(
        self,
        model: str,
        *,
        exclude: set[str],
        prefer: EndpointState | None = None,
    ) -> EndpointState | None:
        """Least-load entre endpoints elegíveis (VRAM + catálogo + healthy)."""
        best: EndpointState | None = None
        best_score = float("inf")

        for ep in self._endpoints:
            if ep.name in exclude:
                continue
            s = ep.score(model)
            # Soft-pin preference: bônus pequeno no endpoint preferido se elegível
            if prefer is not None and ep is prefer and s < float("inf"):
                s -= 3.0
            log.debug(
                "score %s model=%s → %.1f (active=%d vram_free=%.0fMB)",
                ep.name,
                model,
                s,
                ep.active_requests,
                ep.vram_free_mb,
            )
            if s < best_score:
                best_score = s
                best = ep

        if best is None or best_score == float("inf"):
            candidate = max(
                (ep for ep in self._endpoints if ep.healthy and ep.name not in exclude),
                key=lambda ep: ep.vram_free_mb,
                default=None,
            )
            if candidate:
                needed = _estimate_vram_mb(model)
                if self._evict_for_space(candidate, needed):
                    s = candidate.score(model)
                    if prefer is not None and candidate is prefer and s < float("inf"):
                        s -= 3.0
                    if s < float("inf"):
                        best, best_score = candidate, s
            if best is None or best_score == float("inf"):
                return None
        return best

    def pick(self, model: str, exclude: set[str] | None = None) -> EndpointState | None:
        """Retorna o melhor endpoint para o modelo. None se nenhum disponível.

        `exclude` permite failover: endpoints que acabaram de falhar no forward.

        Soft-pin (:gpu0/:gpu1/:nas):
          - Prefere o endpoint pinado quando saudável e com carga baixa.
          - Se ocupado/unhealthy/sem modelo, faz spill para qualquer GPU que
            possua o modelo (distribui carga no cluster).
          - GPU_COORD_SOFT_PIN=0 restaura pin rígido (sem spill).
        """
        exclude = exclude or set()
        prefer: EndpointState | None = None

        for suffix, ep_name in self._PIN_SUFFIX.items():
            if not model.endswith(suffix):
                continue
            pinned = next((ep for ep in self._endpoints if ep.name == ep_name), None)
            if pinned is None:
                log.warning("endpoint pinado %s não configurado para model=%s", ep_name, model)
                break

            pin_ok = (
                pinned.healthy
                and pinned.name not in exclude
                and pinned.has_model_available(model)
            )
            pin_busy = pinned.active_requests >= SOFT_PIN_BUSY_THRESHOLD

            if pin_ok and (not SOFT_PIN or not pin_busy):
                self._ensure_ram_headroom(pinned, model)
                log.info(
                    "roteando model=%s → %s [pinned%s] (active=%d vram_free=%.0fMB)",
                    model,
                    pinned.name,
                    "" if not SOFT_PIN else "/soft",
                    pinned.active_requests,
                    pinned.vram_free_mb,
                )
                return pinned

            if not SOFT_PIN:
                # Pin rígido legado: sem spill.
                if pin_ok:
                    return pinned
                log.warning(
                    "endpoint pinado %s indisponível para model=%s — sem fallback (SOFT_PIN=0)",
                    ep_name,
                    model,
                )
                return None

            # Soft spill: least-load no cluster, ainda preferindo o pin se elegível.
            prefer = pinned if pin_ok else None
            reason = (
                "busy" if pin_ok and pin_busy
                else "unhealthy" if not pinned.healthy
                else "excluded" if pinned.name in exclude
                else "sem-modelo"
            )
            log.info(
                "soft-pin spill model=%s pin=%s reason=%s active=%d — least-load no cluster",
                model,
                pinned.name,
                reason,
                pinned.active_requests,
            )
            break

        best = self._least_load_pick(model, exclude=exclude, prefer=prefer)
        if best is None:
            log.warning("nenhum endpoint elegível para model=%s (mesmo após eviction)", model)
            return None

        log.info(
            "roteando model=%s → %s (active=%d vram_free=%.0fMB%s)",
            model,
            best.name,
            best.active_requests,
            best.vram_free_mb,
            f" prefer={prefer.name}" if prefer else "",
        )
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

        lines.append("# HELP gpu_coord_consecutive_poll_failures Falhas de poll consecutivas por endpoint")
        lines.append("# TYPE gpu_coord_consecutive_poll_failures gauge")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_consecutive_poll_failures{{endpoint="{ep.name}"}} {ep._consec_fails}')

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

        # VRAM por modelo carregado (usada pelos painéis do Grafana)
        lines.append("# HELP ollama_model_ram_mb VRAM usada por modelo carregado em VRAM por endpoint (MB)")
        lines.append("# TYPE ollama_model_ram_mb gauge")
        for ep in self._endpoints:
            for model_name, vram_mb in ep._loaded.items():
                safe = model_name.replace('"', '\\"')
                lines.append(f'ollama_model_ram_mb{{model="{safe}",endpoint="{ep.name}"}} {vram_mb:.1f}')

        # Contagem de modelos carregados por endpoint (painel "Modelos Carregados").
        # Um único timeseries por endpoint canônico — sem aliases gpu0/nas que
        # dobravam painéis no Grafana (2 linhas por placa).
        lines.append("# HELP ollama_loaded_models Número de modelos residentes em VRAM por endpoint")
        lines.append("# TYPE ollama_loaded_models gauge")
        for ep in self._endpoints:
            n_loaded = len(ep._loaded)
            lines.append(f'ollama_loaded_models{{endpoint="{ep.name}"}} {n_loaded}')

        lines.append("# HELP gpu_coord_vram_used_mb VRAM usada estimada por endpoint (MB)")
        lines.append("# TYPE gpu_coord_vram_used_mb gauge")
        for ep in self._endpoints:
            lines.append(f'gpu_coord_vram_used_mb{{endpoint="{ep.name}"}} {ep.vram_used_mb:.1f}')

        # Histograma de latência por modelo (para histogram_quantile no Grafana)
        lines.append("# HELP ollama_request_duration_seconds Latência de requisição por modelo (s)")
        lines.append("# TYPE ollama_request_duration_seconds histogram")
        with _dur_lock:
            for model_name in list(_dur_buckets.keys()):
                safe = model_name.replace('"', '\\"')
                for le, cnt in _dur_buckets[model_name].items():
                    le_str = "+Inf" if le == float("inf") else str(le)
                    lines.append(f'ollama_request_duration_seconds_bucket{{model="{safe}",le="{le_str}"}} {cnt}')
                lines.append(f'ollama_request_duration_seconds_sum{{model="{safe}"}} {_dur_sum[model_name]:.3f}')
                lines.append(f'ollama_request_duration_seconds_count{{model="{safe}"}} {_dur_count[model_name]}')

        # Contadores de request por modelo/endpoint (substitui ollama_generated_tokens quando ausente)
        lines.append("# HELP gpu_coord_model_requests_total Requisições por modelo (via coordinator)")
        lines.append("# TYPE gpu_coord_model_requests_total counter")
        with _dur_lock:
            for model_name, cnt in _dur_count.items():
                safe = model_name.replace('"', '\\"')
                lines.append(f'gpu_coord_model_requests_total{{model="{safe}"}} {cnt}')

        return "\n".join(lines) + "\n"


# ── HTTP handler ──────────────────────────────────────────────────────────────

_cluster: GPUCluster | None = None


class CoordinatorHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args) -> None:
        pass  # silencia log padrão

    # ── leitura ───────────────────────────────────────────────────────────────

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
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
                 streaming: bool) -> bool:
        """Encaminha a requisição para o endpoint escolhido.

        Retorna False se a falha ocorreu *antes* de qualquer byte ser enviado ao
        cliente (conexão recusada, 503/429 busy, etc.) — o caller tenta outra GPU.
        Retorna True se a resposta já foi (ou começou a ser) entregue ao cliente.
        """
        parsed = urllib.parse.urlparse(ep.host)
        host = parsed.hostname
        port = parsed.port or 80

        # Extrai prompt completo para auditoria (ring + PG + painel).
        prompt_preview = ""
        model_name = ""
        try:
            req_data = json.loads(body) if body else {}
            model_name = req_data.get("model", "")
            raw_prompt = req_data.get("prompt") or ""
            if not raw_prompt:
                msgs = req_data.get("messages") or []
                parts: list[str] = []
                for m in msgs:
                    if not isinstance(m, dict):
                        continue
                    role = (m.get("role") or "user").strip()
                    content = m.get("content") or ""
                    if isinstance(content, list):
                        # multimodal: junta textos
                        content = " ".join(
                            (c.get("text") or "") if isinstance(c, dict) else str(c)
                            for c in content
                        )
                    parts.append(f"[{role}] {content}")
                raw_prompt = "\n\n".join(parts)
            # system separado (algumas APIs)
            if req_data.get("system") and "system" not in raw_prompt[:80].lower():
                raw_prompt = f"[system] {req_data['system']}\n\n{raw_prompt}"
            prompt_preview = _clean_text(raw_prompt)
        except Exception:
            pass

        ep.increment(model_name)
        t_start = time.monotonic()
        with _STATS_LOCK:
            global _TOTAL_REQUESTS
            _TOTAL_REQUESTS += 1

        conn = None
        try:
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
            except Exception as exc:
                # Nada foi enviado ao cliente ainda — falha retriável em outro endpoint
                elapsed = round(time.monotonic() - t_start, 2)
                log.warning("conexão com %s falhou (retriável): %s", ep.name, exc)
                _ring_append({
                    "ts":       datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "model":    model_name,
                    "endpoint": ep.name,
                    "path":     path,
                    "status":   503,
                    "elapsed_s": elapsed,
                    "prompt":   prompt_preview,
                    "response": "",
                    "error":    f"connect: {exc}",
                    "streaming": streaming,
                })
                return False

            # 503/429/502/504 do Ollama (ex.: GPU1 NUM_PARALLEL=1 "maximum pending")
            # ANTES de qualquer byte ao cliente → failover para outra GPU.
            if resp.status in _RETRIABLE_BACKEND_STATUS:
                resp_body = b""
                try:
                    resp_body = resp.read()
                except Exception:
                    pass
                err_txt = ""
                try:
                    err_txt = (json.loads(resp_body).get("error") or "")[:200]
                except Exception:
                    err_txt = resp_body[:200].decode(errors="replace") if resp_body else ""
                elapsed = round(time.monotonic() - t_start, 2)
                log.warning(
                    "backend busy %s model=%s status=%d (retriável → failover): %s",
                    ep.name,
                    model_name,
                    resp.status,
                    err_txt,
                )
                _ring_append({
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "model": model_name,
                    "endpoint": ep.name,
                    "path": path,
                    "status": resp.status,
                    "elapsed_s": elapsed,
                    "prompt": prompt_preview,
                    "response": "",
                    "error": f"retriable busy: {err_txt}",
                    "streaming": streaming,
                })
                with _STATS_LOCK:
                    global _REQUEST_ERRORS
                    _REQUEST_ERRORS += 1
                return False

            # A partir daqui a resposta vai ao cliente — sem failover.
            resp_preview = ""
            try:
                if streaming:
                    self.send_response(resp.status)
                    self.send_header(
                        "Content-Type",
                        resp.getheader("Content-Type", "application/json"),
                    )
                    self.send_header("X-GPU-Endpoint", ep.name)
                    # Sem Content-Length: fim do body = fechamento da conexão
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    chunks: list[bytes] = []
                    preview_bytes = 0
                    try:
                        while True:
                            chunk = resp.read(4096)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            if preview_bytes < STREAM_PREVIEW_CAP:
                                chunks.append(chunk)
                                preview_bytes += len(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    try:
                        full = b"".join(chunks).decode(errors="replace")
                        tokens: list[str] = []
                        for ln in full.splitlines():
                            if not ln.strip():
                                continue
                            try:
                                obj = json.loads(ln)
                            except Exception:
                                continue
                            part = obj.get("response") or ""
                            if not part:
                                msg = obj.get("message") or {}
                                if isinstance(msg, dict):
                                    part = msg.get("content") or ""
                            if part:
                                tokens.append(str(part))
                        resp_preview = _clean_text("".join(tokens))
                    except Exception:
                        pass
                else:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    self.send_header(
                        "Content-Type",
                        resp.getheader("Content-Type", "application/json"),
                    )
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.send_header("X-GPU-Endpoint", ep.name)
                    self.end_headers()
                    try:
                        self.wfile.write(resp_body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    try:
                        parsed = json.loads(resp_body)
                        resp_preview = parsed.get("response") or ""
                        if not resp_preview:
                            msg = parsed.get("message") or {}
                            if isinstance(msg, dict):
                                resp_preview = msg.get("content") or ""
                        if not resp_preview and isinstance(parsed.get("messages"), list):
                            for m in reversed(parsed["messages"]):
                                if isinstance(m, dict) and m.get("content"):
                                    resp_preview = m["content"]
                                    break
                        resp_preview = _clean_text(str(resp_preview or ""))
                    except Exception:
                        resp_preview = resp_body[:_PAYLOAD_LOG_CHARS].decode(errors="replace")

                elapsed = round(time.monotonic() - t_start, 2)

                if model_name:
                    _record_duration(model_name, elapsed)

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
                log.info(
                    "✅ %s model=%s → %s status=%d elapsed=%.1fs prompt_chars=%d resp_chars=%d",
                    path,
                    model_name,
                    ep.name,
                    resp.status,
                    elapsed,
                    len(prompt_preview or ""),
                    len(resp_preview or ""),
                )

                if resp.status >= 400:
                    with _STATS_LOCK:
                        _REQUEST_ERRORS += 1
            except Exception as exc:
                # Resposta já pode ter começado — não retentar em outro endpoint
                elapsed = round(time.monotonic() - t_start, 2)
                log.warning("forward para %s falhou durante relay: %s", ep.name, exc)
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
                self.close_connection = True
            return True
        finally:
            # Sempre um decrement por increment (sucesso, busy retriável ou connect fail)
            ep.decrement(model_name)
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def _route_and_forward(self) -> None:
        """Lê body, escolhe GPU, encaminha com failover em busy/conexão."""
        body = self._read_body()
        model = self._extract_model(body)

        # Preferir o flag do body; agenda usa stream=false. Default False evita
        # forçar streaming (que impede failover em 503).
        streaming = False
        try:
            streaming = bool(json.loads(body).get("stream", False))
        except Exception:
            streaming = False

        if _cluster is None:
            self._json_response(503, {"error": "coordinator não inicializado"})
            return

        # Failover: conexão falhou OU backend 503 busy (antes de bytes ao cliente).
        # Não marca unhealthy em busy — a GPU só está com fila cheia.
        tried: set[str] = set()
        for _ in range(len(_cluster._endpoints)):
            ep = _cluster.pick(model, exclude=tried)
            if ep is None:
                break
            ok = self._forward(ep, "POST", self.path, body, streaming)
            if ok:
                return
            tried.add(ep.name)
            log.info(
                "failover: tentando outro endpoint para model=%s (excluídos=%s)",
                model,
                sorted(tried),
            )

        with _STATS_LOCK:
            global _REQUEST_ERRORS
            _REQUEST_ERRORS += 1
        self._json_response(
            503,
            {"error": "nenhum GPU disponível para model=" + model, "tried": sorted(tried)},
        )

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
            # Ring buffer das últimas requisições com preview de prompt/resposta.
            # Sempre HTTP 200 (lista vazia se o ring falhar) — o painel Grafana
            # Infinity trata 5xx/timeout como status 400 no dashboard inteiro.
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                limit = max(1, int(params.get("limit", ["50"])[0]))
            except (TypeError, ValueError):
                limit = 50
            try:
                snapshot = _ring_snapshot()
                if not isinstance(snapshot, list):
                    snapshot = []
            except Exception:
                snapshot = []
            entries = snapshot[:limit]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            body = json.dumps({"requests": entries, "total": len(snapshot)}).encode()
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
                if not self._forward(ep, "POST", self.path, body, streaming=False):
                    ep.mark_unhealthy("falha de conexão no forward")
                    self._json_response(503, {"error": "endpoint primário indisponível", "endpoint": ep.name})
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
    parser.add_argument("--nas-ram-exporter",
                         default=os.environ.get("OLLAMA_NAS_RAM_EXPORTER_HOST", "http://192.168.15.4:11447"))
    args = parser.parse_args()

    endpoints = [
        EndpointState("gpu0-rtx3060", args.gpu0, vram_total_mb=12 * 1024, priority=0),  # ~170 GFLOPS FP32
        EndpointState("nas-rtx2060",  args.nas,  vram_total_mb=8 * 1024,  priority=1,   # ~57 GFLOPS FP32
                       ram_exporter_host=args.nas_ram_exporter),  # gargalo real é RAM do host, não VRAM
        EndpointState("gpu1-gtx1050", args.gpu1, vram_total_mb=2 * 1024,  priority=2),  # ~19 GFLOPS FP32
    ]

    _cluster = GPUCluster(endpoints)
    _cluster.start_poller()
    _start_pg_writer()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), CoordinatorHandler)
    server.daemon_threads = True

    def _graceful_stop(signum, _frame) -> None:
        log.info("sinal %d recebido — encerrando", signum)
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _graceful_stop)

    log.info("🚀 GPU Coordinator v2 iniciado na porta %d", args.port)
    for ep in endpoints:
        log.info("   %s  %s  %dGB  healthy=%s  modelos=%s",
                 ep.name, ep.host, ep.vram_total_mb // 1024, ep.healthy,
                 list(ep._loaded.keys()))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _cluster.stop()
        server.server_close()
        log.info("Coordenador encerrado.")


if __name__ == "__main__":
    main()
