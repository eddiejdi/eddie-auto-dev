#!/usr/bin/env python3
"""Mantém um modelo Ollama permanentemente carregado no host configurado.

Monitora /api/ps e, se o modelo sumir da lista de modelos carregados,
envia uma geração mínima com keep_alive=-1 para recolocá-lo na VRAM.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_PIN_MODEL", "eddie-sentiment:latest")
CHECK_INTERVAL = int(os.environ.get("OLLAMA_PIN_CHECK_INTERVAL", "30"))
TIMEOUT = int(os.environ.get("OLLAMA_PIN_TIMEOUT", "120"))
MODEL_EQUIVALENTS = {
    "eddie-sentiment:latest": {"phi4-mini", "phi4-mini:latest"},
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [ollama-pin] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ollama-pin")


def _request(url: str, payload: dict | None = None, timeout: int = TIMEOUT) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def is_loaded() -> bool:
    data = _request(f"{OLLAMA_HOST}/api/ps", timeout=5)
    loaded = [m.get("name", "") for m in data.get("models", [])]
    valid_names = {MODEL, MODEL.removesuffix(":latest")}
    valid_names.update(MODEL_EQUIVALENTS.get(MODEL, set()))
    return any(name in valid_names for name in loaded)


def warm() -> None:
    start = time.monotonic()
    _request(
        f"{OLLAMA_HOST}/api/generate",
        payload={
            "model": MODEL,
            "prompt": "ping",
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 1, "temperature": 0.0},
        },
    )
    logger.info("%s pinned in %.3fs", MODEL, time.monotonic() - start)


def main() -> int:
    logger.info("starting pin watchdog for %s on %s", MODEL, OLLAMA_HOST)
    while True:
        try:
            if not is_loaded():
                logger.warning("%s not loaded; rewarming now", MODEL)
                warm()
        except urllib.error.URLError as exc:
            logger.warning("ollama unavailable: %s", exc)
        except Exception as exc:
            logger.warning("pin loop error: %s", exc)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
