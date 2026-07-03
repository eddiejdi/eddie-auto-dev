#!/usr/bin/env python3
"""Warmup HTTP nao bloqueante para instancias Ollama gerenciadas por systemd."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _post_json(url: str, payload: dict, timeout: float) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "ollama-warmup/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Base URL da instancia Ollama")
    parser.add_argument("--default-model", required=True, help="Modelo se OLLAMA_PRELOAD_MODEL nao estiver definido")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--delay", type=float, default=8.0)
    args = parser.parse_args()

    if args.delay > 0:
        time.sleep(args.delay)

    model = os.getenv("OLLAMA_PRELOAD_MODEL") or args.default_model
    payload = {
        "model": model,
        "prompt": "ping",
        "stream": False,
        "options": {"num_predict": 1},
    }
    try:
        _post_json(f"{args.host.rstrip('/')}/api/generate", payload, args.timeout)
        print(f"ollama warmup ok: {model} @ {args.host}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"ollama warmup skipped: {model} @ {args.host}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
