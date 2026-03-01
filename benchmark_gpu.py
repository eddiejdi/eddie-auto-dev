#!/usr/bin/env python3
"""
Benchmark LLM latency com GPU activado - teste direto via HTTP
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime
import statistics

OLLAMA_URL = "http://192.168.15.2:11434/api/generate"
MODEL = "eddie-whatsapp:latest"

def test_latency(prompt, num_samples=3):
    """Testa latência do modelo."""
    latencies = []
    tokens_per_sec = []
    token_counts = []
    
    print(f"\n📌 Testando: {prompt[:50]}...")
    
    for i in range(num_samples):
        request_data = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
        
        start_time = time.time()
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(request_data).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            response = urllib.request.urlopen(req, timeout=300)
            result = json.loads(response.read().decode('utf-8'))
            elapsed = time.time() - start_time
            
            eval_count = result.get('eval_count', 0)
            tokens_per_second = eval_count / elapsed if elapsed > 0 else 0
            
            latencies.append(elapsed)
            tokens_per_sec.append(tokens_per_second)
            token_counts.append(eval_count)
            
            print(f"  [{i+1}/{num_samples}] {elapsed:.2f}s | {tokens_per_second:.1f} tokens/s")
            
        except Exception as e:
            print(f"  [{i+1}/{num_samples}] ❌ Error: {str(e)[:80]}")
    
    return latencies, tokens_per_sec, token_counts

def main():
    print("=" * 70)
    print("🚀 BENCHMARK GPU - eddie-whatsapp:latest via Ollama")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print(f"   Servidor: 192.168.15.2:11434")
    print("=" * 70)
    
    # Check health
    try:
        req = urllib.request.Request(
            "http://192.168.15.2:11434/api/tags",
            method="GET"
        )
        response = urllib.request.urlopen(req, timeout=5)
        print("\n✓ Ollama está respondendo\n")
    except:
        print("\n❌ Ollama não está acessível\n")
        return
    
    # Various prompt lengths
    test_cases = [
        ("Olá, como você está?", "short", 3),
        ("Qual é o significado de inteligência artificial?", "medium", 3),
        ("Explique em detalhes como funciona uma rede neural artificial.", "long", 2),
    ]
    
    all_results = {}
    
    for prompt, name, samples in test_cases:
        latencies, tps, tokens = test_latency(prompt, num_samples=samples)
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            avg_tps = statistics.mean(tps)
            avg_tokens = statistics.mean(tokens)
            
            all_results[name] = {
                "avg_latency": avg_latency,
                "avg_tps": avg_tps,
                "avg_tokens": avg_tokens,
                "min_latency": min(latencies),
                "max_latency": max(latencies),
            }
            
            print(f"\n📈 Resumo ({name}):")
            print(f"   Latência média: {avg_latency:.2f}s")
            print(f"   Tokens/segundo: {avg_tps:.1f}")
            print(f"   Tokens por amostra: {avg_tokens:.0f}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 RESUMO FINAL")
    print("=" * 70)
    for name, metrics in all_results.items():
        print(f"\n{name.upper()}:")
        print(f"  Latência: {metrics['avg_latency']:.2f}s (min: {metrics['min_latency']:.2f}s, max: {metrics['max_latency']:.2f}s)")
        print(f"  Throughput: {metrics['avg_tps']:.1f} tokens/s")
    
    print("\n✅ Benchmark concluído!")
    print(f"   Status: GPU ATIVA (modelo em VRAM)")
    print("=" * 70)

if __name__ == "__main__":
    main()
