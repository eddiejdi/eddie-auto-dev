#!/usr/bin/env python3
"""Gera carga útil no Ollama da NAS (RTX 2060) via coordenador (:11437).

Usa modelos com sufixo :nas (pinados pelo ollama-gpu-coordinator) para garantir
que a inferência rode em 192.168.15.4:11436 e não na GPU0 do homelab.

Uso:
  python3 scripts/nas_ollama_load.py              # 1 batch
  python3 scripts/nas_ollama_load.py --loops 5    # 5 rounds
  python3 scripts/nas_ollama_load.py --direct     # bate direto na NAS, sem coord
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

COORD = os.environ.get("OLLAMA_COORD_HOST", "http://192.168.15.2:11437")
NAS = os.environ.get("OLLAMA_NAS_HOST", "http://192.168.15.4:11436")

# Modelos pinados :nas (criados no Ollama da NAS)
DEFAULT_MODELS = [
    "phi4-mini:nas",
    "llama3.1-8b:nas",
    "eddie-persona-safe:nas",
]

PROMPTS = [
    "Resuma em 1 frase o papel de um coordenador de GPUs Ollama.",
    "Liste 3 riscos de trading crypto e uma mitigação curta para cada.",
    "Explique keep-alive de modelo Ollama em 2 frases.",
    "Gere um checklist de health check de NAS com GPU (5 bullets).",
]


def _post_generate(base: str, model: str, prompt: str, timeout: int) -> dict:
    url = f"{base.rstrip('/')}/api/generate"
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 64, "temperature": 0.3},
        }
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    elapsed = time.monotonic() - t0
    return {
        "model": model,
        "ok": True,
        "elapsed_s": round(elapsed, 2),
        "response": (data.get("response") or "")[:120],
        "eval_count": data.get("eval_count"),
    }


def _one(base: str, model: str, prompt: str, timeout: int) -> dict:
    try:
        return _post_generate(base, model, prompt, timeout)
    except Exception as exc:  # noqa: BLE001 — report all load errors
        return {"model": model, "ok": False, "error": str(exc)[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--direct", action="store_true", help="NAS direta, sem coordenador")
    ap.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="CSV de modelos (prefira sufixo :nas)",
    )
    args = ap.parse_args()
    base = NAS if args.direct else COORD
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print(f"target={base} models={models} loops={args.loops} workers={args.workers}")
    ok = 0
    fail = 0
    for loop in range(1, args.loops + 1):
        jobs = []
        for i, model in enumerate(models):
            prompt = PROMPTS[(loop + i) % len(PROMPTS)]
            jobs.append((model, prompt))

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = [
                pool.submit(_one, base, model, prompt, args.timeout)
                for model, prompt in jobs
            ]
            for fut in as_completed(futs):
                r = fut.result()
                if r.get("ok"):
                    ok += 1
                    print(
                        f"[ok] loop={loop} model={r['model']} "
                        f"{r['elapsed_s']}s eval={r.get('eval_count')} "
                        f"→ {r.get('response', '')!r}"
                    )
                else:
                    fail += 1
                    print(f"[fail] loop={loop} model={r.get('model')} err={r.get('error')}")

    # Health snapshot if using coordinator
    if not args.direct:
        try:
            with urllib.request.urlopen(f"{COORD}/health", timeout=5) as resp:
                health = json.loads(resp.read().decode())
            for ep in health.get("endpoints", []):
                print(
                    f"health {ep['name']}: served={ep.get('total_served')} "
                    f"active={ep.get('active_requests')} loaded={ep.get('loaded_models')}"
                )
        except Exception as exc:  # noqa: BLE001
            print(f"health check failed: {exc}", file=sys.stderr)

    print(f"done ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
