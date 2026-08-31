import os
import requests
import time

# try environment variable first, fallback to localhost
OLLAMA_URL = (
    os.environ.get("OLLAMA_URL")
    or "http://localhost:11434/api/generate"
)


models = [
    "qwen3:0.6b",
    "qwen3:4b",
    "qwen3:14b",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
]

# tests/prompts for every model
# keep only short and count tests to avoid long-running timeouts
prompts = {
    "short": "Hi",
    "count": "Count from 1 to 100",
}

results = []

if __name__ == "__main__":
    print("Running Ollama model benchmarks")
    for model in models:
        for testname, prompt in prompts.items():
            payload = {"model": model, "prompt": prompt, "stream": False}
            t0 = time.time()
            try:
                r = requests.post(OLLAMA_URL, json=payload, timeout=120)
                dt = time.time() - t0
                length = len(r.text)
                results.append((model, testname, dt, length))
                print(f"{model:20} | {testname:6} | {dt:.2f}s | {length} chars")
            except Exception as e:
                dt = time.time() - t0
                results.append((model, testname, None, str(e)))
                print(f"{model:20} | {testname:6} | FAILED after {dt:.2f}s ({e})")
    # print summary table
    print("\n### Summary")
    print("| Model | Test | Latency (s) | Output size |")
    print("|-------|------|-------------|-------------|")
    for model, testname, dt, length in results:
        print(f"| {model} | {testname} | {dt:.2f} | {length} |")
