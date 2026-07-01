#!/usr/bin/env python3
"""
LLM Router — roteamento multi-GPU para o trading agent.

Gerencia 3 endpoints Ollama:
  GPU0  homelab:11434 — RTX 3060 12GB   (modelos pesados: trading-analyst)
  GPU1  homelab:11435 — GTX 1050 2GB    (modelos leves: gemma3:1b)
  NAS   192.168.15.4:11436 — RTX 2060 SUPER 8GB (média carga, CPU até driver NVIDIA)

Uso simples no trading agent:
    from llm import LLMRouter
    router = LLMRouter()
    result = router.generate("trading-analyst", prompt, timeout=60)
    result = router.chat("gemma3:1b", messages, timeout=30)
"""

import os
import re
import time
import random
import logging
import fcntl
import tempfile
import contextlib
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint registry
# ---------------------------------------------------------------------------

@dataclass
class OllamaEndpoint:
    name: str
    host: str
    # Models this endpoint is the *primary* home for (exact match or prefix)
    primary_models: List[str] = field(default_factory=list)
    # Health state (updated lazily)
    _healthy: Optional[bool] = field(default=None, init=False, repr=False)
    _last_health_check: float = field(default=0.0, init=False, repr=False)
    _health_ttl: float = field(default=30.0, init=False, repr=False)

    def is_healthy(self, probe_timeout: float = 3.0) -> bool:
        now = time.monotonic()
        if self._healthy is not None and (now - self._last_health_check) < self._health_ttl:
            return self._healthy
        try:
            with httpx.Client(timeout=probe_timeout) as c:
                r = c.get(f"{self.host}/api/tags")
            self._healthy = r.status_code == 200
        except Exception:
            self._healthy = False
        self._last_health_check = now
        return self._healthy

    def invalidate_health(self):
        self._healthy = None


# Default endpoints — apontam para os proxies ollama-metrics (coletam métricas
# transparentemente e encaminham para o Ollama real).
# Portas diretas como fallback via LLM_GPU0_HOST_DIRECT etc.
def _default_endpoints() -> List[OllamaEndpoint]:
    gpu0_host = os.getenv("LLM_GPU0_HOST", "http://192.168.15.2:11544")   # proxy → 11434
    gpu1_host = os.getenv("LLM_GPU1_HOST", "http://192.168.15.2:11545")   # proxy → 11435
    nas_host  = os.getenv("LLM_NAS_HOST",  "http://192.168.15.4:11546")   # proxy → 11436
    return [
        OllamaEndpoint(
            name="gpu0-rtx3060",
            host=gpu0_host,
            primary_models=["trading-analyst"],
        ),
        OllamaEndpoint(
            name="gpu1-gtx1050",
            host=gpu1_host,
            primary_models=["gemma3:1b"],
        ),
        OllamaEndpoint(
            name="nas-rtx2060",
            host=nas_host,
            primary_models=["mistral:7b"],
        ),
    ]


# ---------------------------------------------------------------------------
# Inter-process gate (same as trading_agent._ollama_host_gate)
# ---------------------------------------------------------------------------

_gate_logger = logging.getLogger("llm.gate")


@contextlib.contextmanager
def _host_gate(host: str, timeout: float = 20.0):
    m = re.search(r":(\d{4,5})(?:/|$)", host)
    port = m.group(1) if m else re.sub(r"[^a-zA-Z0-9]", "_", host)
    gate_dir = tempfile.gettempdir() + "/ollama-gate"
    os.makedirs(gate_dir, exist_ok=True)
    lock_path = f"{gate_dir}/ollama_{port}.lock"

    acquired = False
    fh = None
    try:
        fh = open(lock_path, "w")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                time.sleep(random.uniform(0.05, 0.25))
                break
            except OSError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _gate_logger.warning(
                        "⏳ gate timeout (%.0fs) porta %s — prosseguindo sem lock", timeout, port
                    )
                    break
                time.sleep(min(0.15, remaining))
        yield
    finally:
        if fh is not None:
            if acquired:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            try:
                fh.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------

class LLMRouter:
    """
    Router unificado para os 3 endpoints Ollama do cluster.

    Roteamento:
    1. Se o modelo está em `primary_models` de um endpoint, esse endpoint é o primário.
    2. Endpoints secundários são os outros, em ordem de prioridade (gpu0 > gpu1 > nas).
    3. Health check lazy com TTL 30s — endpoint doente é pulado e o próximo é tentado.
    """

    # Timeouts de gate globais
    GATE_TIMEOUT_MIN_SEC: float = 200.0
    GATE_TIMEOUT_MULTIPLIER: float = 2.5

    def __init__(self, endpoints: Optional[List[OllamaEndpoint]] = None):
        self._endpoints = endpoints or _default_endpoints()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _resolve_order(self, model: str) -> List[OllamaEndpoint]:
        """Retorna lista de endpoints na ordem de tentativa para `model`."""
        primary = []
        secondary = []
        for ep in self._endpoints:
            is_primary = any(
                model == pm or model.startswith(pm.split(":")[0])
                for pm in ep.primary_models
            )
            (primary if is_primary else secondary).append(ep)
        return primary + secondary

    def _pick_endpoint(self, model: str, probe_timeout: float = 3.0) -> Optional[OllamaEndpoint]:
        """Retorna primeiro endpoint saudável para o modelo, ou None."""
        for ep in self._resolve_order(model):
            if ep.is_healthy(probe_timeout):
                return ep
        return None

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _do_generate(
        self,
        host: str,
        model: str,
        prompt: str,
        options: Dict[str, Any],
        timeout: float,
        use_chat: bool,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Faz a chamada HTTP e retorna o texto bruto da resposta."""
        gate_timeout = max(
            self.GATE_TIMEOUT_MIN_SEC,
            timeout * self.GATE_TIMEOUT_MULTIPLIER,
        )
        with _host_gate(host, timeout=gate_timeout):
            with httpx.Client(timeout=float(timeout)) as client:
                if use_chat:
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    resp = client.post(
                        f"{host}/api/chat",
                        json={
                            "model": model,
                            "messages": messages,
                            "stream": False,
                            "format": "json",
                            "options": options,
                        },
                    )
                    resp.raise_for_status()
                    return (resp.json().get("message") or {}).get("content", "").strip()
                else:
                    resp = client.post(
                        f"{host}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "stream": False,
                            "format": "json",
                            "options": options,
                        },
                    )
                    resp.raise_for_status()
                    return resp.json().get("response", "").strip()

    def _do_chat(
        self,
        host: str,
        model: str,
        messages: List[Dict[str, str]],
        options: Dict[str, Any],
        timeout: float,
    ) -> str:
        gate_timeout = max(
            self.GATE_TIMEOUT_MIN_SEC,
            timeout * self.GATE_TIMEOUT_MULTIPLIER,
        )
        with _host_gate(host, timeout=gate_timeout):
            with httpx.Client(timeout=float(timeout)) as client:
                resp = client.post(
                    f"{host}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "format": "json",
                        "options": options,
                    },
                )
                resp.raise_for_status()
                return (resp.json().get("message") or {}).get("content", "").strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        timeout: float = 60.0,
        fallback_timeout: float | None = None,
        options: Dict[str, Any] | None = None,
        system_prompt: str | None = None,
        use_chat: bool | None = None,
        probe_timeout: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Envia `prompt` para o melhor endpoint disponível para `model`.

        Retorna dict com: text, host, endpoint_name, model, latency_ms, fallback_used.
        Lança RuntimeError se todos os endpoints falharem.
        """
        opts = options or {}
        if use_chat is None:
            use_chat = "instruct" in model.lower()
        ft = fallback_timeout or timeout

        order = self._resolve_order(model)
        errors: list[str] = []

        for i, ep in enumerate(order):
            if not ep.is_healthy(probe_timeout):
                errors.append(f"{ep.name}: unhealthy")
                continue
            t = timeout if i == 0 else ft
            started = time.time()
            try:
                text = self._do_generate(ep.host, model, prompt, opts, t, use_chat, system_prompt)
                latency_ms = (time.time() - started) * 1000.0
                logger.debug(
                    "LLM %s@%s → %.0fms (fallback=%s)", model, ep.name, latency_ms, i > 0
                )
                return {
                    "text": text,
                    "host": ep.host,
                    "endpoint_name": ep.name,
                    "model": model,
                    "latency_ms": round(latency_ms, 2),
                    "fallback_used": i > 0,
                }
            except Exception as exc:
                ep.invalidate_health()
                errors.append(f"{ep.name}/{model}: {type(exc).__name__}: {exc}")
                logger.warning("LLM falhou em %s: %s", ep.name, exc)

        raise RuntimeError(
            f"LLMRouter.generate({model!r}) falhou em {len(order)} endpoints: "
            + " | ".join(errors[:4])
        )

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        *,
        timeout: float = 60.0,
        fallback_timeout: float | None = None,
        options: Dict[str, Any] | None = None,
        probe_timeout: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Envia `messages` (formato OpenAI) para o melhor endpoint.
        Retorna mesmo dict que generate().
        """
        opts = options or {}
        ft = fallback_timeout or timeout
        order = self._resolve_order(model)
        errors: list[str] = []

        for i, ep in enumerate(order):
            if not ep.is_healthy(probe_timeout):
                errors.append(f"{ep.name}: unhealthy")
                continue
            t = timeout if i == 0 else ft
            started = time.time()
            try:
                text = self._do_chat(ep.host, model, messages, opts, t)
                latency_ms = (time.time() - started) * 1000.0
                return {
                    "text": text,
                    "host": ep.host,
                    "endpoint_name": ep.name,
                    "model": model,
                    "latency_ms": round(latency_ms, 2),
                    "fallback_used": i > 0,
                }
            except Exception as exc:
                ep.invalidate_health()
                errors.append(f"{ep.name}/{model}: {type(exc).__name__}: {exc}")
                logger.warning("LLM chat falhou em %s: %s", ep.name, exc)

        raise RuntimeError(
            f"LLMRouter.chat({model!r}) falhou em {len(order)} endpoints: "
            + " | ".join(errors[:4])
        )

    def request(
        self,
        model: str,
        prompt: str,
        *,
        timeout: float = 60.0,
        fallback_timeout: float | None = None,
        options: Dict[str, Any] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Atalho: retorna só o texto (para migração rápida de chamadas legadas)."""
        return self.generate(
            model, prompt,
            timeout=timeout,
            fallback_timeout=fallback_timeout,
            options=options,
            system_prompt=system_prompt,
        )["text"]

    def health_summary(self, probe_timeout: float = 3.0) -> Dict[str, bool]:
        """Retorna dict {endpoint_name: is_healthy} para monitoramento."""
        return {ep.name: ep.is_healthy(probe_timeout) for ep in self._endpoints}

    def endpoint_for(self, host: str) -> Optional[OllamaEndpoint]:
        """Retorna o endpoint que corresponde ao host (para compatibilidade com código legado)."""
        for ep in self._endpoints:
            if ep.host == host or ep.host.rstrip("/") == host.rstrip("/"):
                return ep
        return None

    # ------------------------------------------------------------------
    # Compatibility shim for trading_agent._request_ollama_structured
    # ------------------------------------------------------------------

    def request_structured(
        self,
        *,
        label: str,
        prompt: str,
        primary_host: str,
        primary_model: str,
        fallback_host: str,
        fallback_model: str,
        primary_timeout_sec: float,
        fallback_timeout_sec: float,
        options: Dict[str, Any],
        parser,
        retries_per_target: int = 1,
    ) -> tuple[Any, str, Dict[str, Any]]:
        """
        Drop-in replacement para trading_agent._request_ollama_structured.

        Mantém a assinatura exata para facilitar a migração gradual.
        Após os pares explícitos falharem, tenta endpoints adicionais do router
        (ex: NAS) com o fallback_model como terceiro tier.
        """
        explicit_pairs: list[tuple[str, str, float]] = []
        seen: set[tuple[str, str]] = set()
        for host, model, t in [
            (primary_host, primary_model, primary_timeout_sec),
            (fallback_host, fallback_model, fallback_timeout_sec),
        ]:
            host = (host or "").strip()
            model = (model or "").strip()
            if not host or not model:
                continue
            key = (host, model)
            if key in seen:
                continue
            seen.add(key)
            for _ in range(max(1, int(retries_per_target))):
                explicit_pairs.append((host, model, t))

        # Terceiro tier: endpoints do router não incluídos acima
        tried_hosts = {h for h, _, _ in explicit_pairs}
        extra_pairs: list[tuple[str, str, float]] = []
        extra_model = (fallback_model or primary_model).strip()
        for ep in self._endpoints:
            if ep.host not in tried_hosts and ep.is_healthy(probe_timeout=2.0):
                extra_pairs.append((ep.host, extra_model, fallback_timeout_sec))

        all_attempts = explicit_pairs + extra_pairs
        errors: list[str] = []
        use_chat = "instruct" in primary_model.lower()

        for attempt_no, (host, model, timeout_sec) in enumerate(all_attempts, start=1):
            started = time.time()
            target_index = 1 if (host, model) in {(h, m) for h, m, _ in explicit_pairs[:1]} else (
                2 if (host, model) in {(h, m) for h, m, _ in explicit_pairs[1:]} else 3
            )
            try:
                text = self._do_generate(host, model, prompt, options, timeout_sec, use_chat)
                latency_ms = (time.time() - started) * 1000.0
                parsed = parser(text)
                if target_index >= 3:
                    logger.info("LLM %s: terceiro tier (%s) usou %s@%s", label, attempt_no, model, host)
                return parsed, text, {
                    "host": host,
                    "model": model,
                    "latency_ms": round(latency_ms, 2),
                    "attempt": attempt_no,
                    "fallback_used": target_index > 1,
                }
            except Exception as exc:
                errors.append(f"{model}@{host}#{attempt_no}: {type(exc).__name__}: {exc}")

        raise RuntimeError(
            f"{label} failed after {len(all_attempts)} attempts: " + " | ".join(errors[:4])
        )


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_router: Optional[LLMRouter] = None
_router_lock = threading.Lock()


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = LLMRouter()
    return _router


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    router = LLMRouter()

    print("\n=== Health Check ===")
    health = router.health_summary()
    for name, ok in health.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    print("\n=== Endpoint routing for models ===")
    for model in ["trading-analyst", "gemma3:1b", "mistral:7b"]:
        order = router._resolve_order(model)
        print(f"  {model:30s} → {[ep.name for ep in order]}")
