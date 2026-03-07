#!/usr/bin/env python3
"""Benchmark de inferência para GPU1 (GTX 1050) — mede tokens/s e latência.

Executa múltiplas inferências no Ollama GPU1 (:11435) e reporta estatísticas.
Usar antes e depois de otimizações para comparar performance.

Uso:
    python tools/benchmark_gpu1.py [--runs N] [--model MODEL] [--host HOST]
"""
import argparse
import json
import statistics
import time
from typing import Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError


PROMPTS = [
    {"prompt": "What is 2+2? Answer in one word.", "max_tokens": 20},
    {"prompt": "Explain Bitcoin in 3 sentences.", "max_tokens": 100},
    {"prompt": "List 5 programming languages.", "max_tokens": 60},
    {"prompt": "Translate 'hello world' to Portuguese, Spanish and French.", "max_tokens": 50},
    {"prompt": "Write a haiku about the moon.", "max_tokens": 40},
]


def run_inference(host: str, model: str, prompt: str, max_tokens: int) -> Dict:
    """Executa uma inferência e retorna métricas."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode()

    req = Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.monotonic()
    try:
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except URLError as e:
        return {"error": str(e)}
    elapsed = time.monotonic() - t0

    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 1)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_ns = data.get("prompt_eval_duration", 1)
    load_ns = data.get("load_duration", 0)

    tok_per_sec = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0
    prompt_tok_per_sec = prompt_eval_count / (prompt_eval_ns / 1e9) if prompt_eval_ns > 0 else 0

    return {
        "eval_tokens": eval_count,
        "eval_tok_per_sec": tok_per_sec,
        "prompt_tokens": prompt_eval_count,
        "prompt_tok_per_sec": prompt_tok_per_sec,
        "total_ms": elapsed * 1000,
        "load_ms": load_ns / 1e6,
        "eval_ms": eval_duration_ns / 1e6,
    }


def run_benchmark(host: str, model: str, runs: int) -> List[Dict]:
    """Executa benchmark completo com múltiplas rodadas."""
    results = []

    # Warmup (1 inferência descartada)
    print(f"🔥 Warmup ({model} @ {host})...")
    run_inference(host, model, "Hi", 5)

    for run in range(1, runs + 1):
        print(f"\n📊 Rodada {run}/{runs}")
        for i, p in enumerate(PROMPTS):
            r = run_inference(host, model, p["prompt"], p["max_tokens"])
            if "error" in r:
                print(f"  ❌ Prompt {i+1}: {r['error']}")
                continue
            results.append(r)
            print(
                f"  Prompt {i+1}: {r['eval_tok_per_sec']:.1f} tok/s "
                f"({r['eval_tokens']} tokens em {r['eval_ms']:.0f}ms) "
                f"| prompt: {r['prompt_tok_per_sec']:.0f} tok/s"
            )

    return results


def print_summary(results: List[Dict], model: str) -> None:
    """Imprime resumo estatístico."""
    if not results:
        print("❌ Nenhum resultado válido")
        return

    tok_rates = [r["eval_tok_per_sec"] for r in results]
    prompt_rates = [r["prompt_tok_per_sec"] for r in results]
    total_ms = [r["total_ms"] for r in results]

    print(f"\n{'='*60}")
    print(f"📈 BENCHMARK SUMMARY — {model}")
    print(f"{'='*60}")
    print(f"  Runs válidas: {len(results)}")
    print(f"  Generation (tok/s):")
    print(f"    Mean:   {statistics.mean(tok_rates):.1f}")
    print(f"    Median: {statistics.median(tok_rates):.1f}")
    print(f"    Min:    {min(tok_rates):.1f}")
    print(f"    Max:    {max(tok_rates):.1f}")
    if len(tok_rates) > 1:
        print(f"    StdDev: {statistics.stdev(tok_rates):.1f}")
    print(f"  Prompt eval (tok/s):")
    print(f"    Mean:   {statistics.mean(prompt_rates):.0f}")
    print(f"    Median: {statistics.median(prompt_rates):.0f}")
    print(f"  Latency total (ms):")
    print(f"    Mean:   {statistics.mean(total_ms):.0f}")
    print(f"    Median: {statistics.median(total_ms):.0f}")
    print(f"    P95:    {sorted(total_ms)[int(len(total_ms)*0.95)]:.0f}")
    print(f"{'='*60}")


def main() -> None:
    """Ponto de entrada do benchmark GPU1."""
    parser = argparse.ArgumentParser(description="Benchmark GPU1 (GTX 1050)")
    parser.add_argument("--runs", type=int, default=2, help="Número de rodadas")
    parser.add_argument("--model", default="qwen3:0.6b", help="Modelo Ollama")
    parser.add_argument("--host", default="http://192.168.15.2:11435", help="Ollama GPU1 URL")
    args = parser.parse_args()

    print(f"🚀 Benchmark GPU1: {args.model} @ {args.host}")
    print(f"   Rodadas: {args.runs} × {len(PROMPTS)} prompts = {args.runs * len(PROMPTS)} inferências")

    results = run_benchmark(args.host, args.model, args.runs)
    print_summary(results, args.model)


if __name__ == "__main__":
    main()
