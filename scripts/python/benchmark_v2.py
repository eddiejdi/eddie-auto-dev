#!/usr/bin/env python3
"""
Serialized Ollama benchmark - roda 1 modelo por vez
"""
import os
import requests
import time
import subprocess
import json

OLLAMA_URL = os.environ.get("OLLAMA_URL") or "http://localhost:11434/api/generate"

models = [
    "qwen3:0.6b",
    "qwen3:4b",
    "qwen3:14b",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
]

prompts = {
    "short": "Hi",
    "count": "Count from 1 to 100",
}

results = []

if __name__ == "__main__":
    print("=== Serialized Ollama Benchmark ===\n")

    for model in models:
        print(f"\n--- Testing {model} ---")
        
        for testname, prompt in prompts.items():
            payload = {"model": model, "prompt": prompt, "stream": False}
            t0 = time.time()
            
            try:
                # Aumentar timeout para 300s (5 min) por model grande
                r = requests.post(OLLAMA_URL, json=payload, timeout=300)
                dt = time.time() - t0
                
                if r.status_code == 200:
                    data = r.json()
                    output_len = len(data.get("response", ""))
                    results.append({
                        "model": model,
                        "test": testname,
                        "latency": dt,
                        "output_size": output_len,
                        "status": "OK"
                    })
                    print(f"  {testname:8} | {dt:7.2f}s | {output_len:6} chars ✓")
                else:
                    dt = time.time() - t0
                    results.append({
                        "model": model,
                        "test": testname,
                        "latency": None,
                        "output_size": None,
                        "status": f"HTTP {r.status_code}"
                    })
                    print(f"  {testname:8} | HTTP {r.status_code} after {dt:.2f}s ✗")
                    
            except requests.exceptions.Timeout:
                dt = time.time() - t0
                results.append({
                    "model": model,
                    "test": testname,
                    "latency": None,
                    "output_size": None,
                    "status": f"TIMEOUT after {dt:.0f}s"
                })
                print(f"  {testname:8} | TIMEOUT after {dt:.0f}s ✗")
                
            except Exception as e:
                dt = time.time() - t0
                results.append({
                    "model": model,
                    "test": testname,
                    "latency": None,
                    "output_size": None,
                    "status": str(e)[:30]
                })
                print(f"  {testname:8} | ERROR: {str(e)[:40]} ✗")

    # Print final summary table
    print("\n\n=== RESULTS SUMMARY ===\n")
    print("| Model | Test | Latency (s) | Output Size | Status |")
    print("|-------|------|-------------|-------------|--------|")
    
    for r in results:
        model = r["model"]
        test = r["test"]
        latency = f"{r['latency']:.2f}" if r["latency"] is not None else "—"
        output_size = str(r["output_size"]) if r["output_size"] is not None else "—"
        status = "✓" if r["status"] == "OK" else "✗"
        print(f"| {model:20} | {test:6} | {latency:11} | {output_size:11} | {status:6} |")

    # Save JSON results
    with open("/tmp/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n\nResults saved to /tmp/benchmark_results.json")
