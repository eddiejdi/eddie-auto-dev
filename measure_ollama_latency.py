#!/usr/bin/env python3
"""
Mede o tempo de resposta do modelo shared-whatsapp:latest via Ollama no homelab.
"""

import subprocess
import json
import time
import statistics
import sys
from datetime import datetime

HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
OLLAMA_PORT = 11434
MODEL_NAME = "shared-whatsapp:latest"

def run_ssh_command(cmd):
    """Executa comando via SSH no homelab."""
    try:
        result = subprocess.run(
            ["ssh", f"{HOMELAB_USER}@{HOMELAB_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.stdout.strip(), result.returncode, result.stderr.strip()
    except Exception as e:
        print(f"❌ Erro SSH: {e}")
        return None, -1, str(e)

def check_ollama_health():
    """Verifica a saúde do Ollama."""
    cmd = f"curl -s http://localhost:{OLLAMA_PORT}/api/tags -m 5 | head -1"
    output, code, _ = run_ssh_command(cmd)
    
    if code == 0 and output and "{" in output:
        print(f"✓ Ollama está respondendo")
        return True
    print("❌ Ollama não está respondendo")
    return False

def test_model_latency(num_samples=5, prompt_type="short"):
    """Testa latência do modelo Ollama."""
    
    prompts = {
        "short": "Olá, como você está?",
        "medium": "Qual é o significado de inteligência artificial?",
        "long": "Explique em detalhes como funciona uma rede neural artificial, desde os neurônios artificiais até as camadas profundas."
    }
    
    prompt = prompts.get(prompt_type, prompts["short"])
    
    print(f"\n📊 Testando {num_samples} inferências (modelo: {MODEL_NAME})")
    print(f"   Prompt: '{prompt[:60]}...'")
    print(f"   Tipo: {prompt_type}\n")
    
    latencies = []
    tokens_per_sec = []
    
    for i in range(num_samples):
        # Cria comando Python que será executado no homelab
        python_cmd = f"""
import json
import time
import urllib.request
import urllib.error

prompt = {json.dumps(prompt)}
request_data = {{
    "model": "{MODEL_NAME}",
    "prompt": prompt,
    "stream": False
}}

start_time = time.time()
try:
    req = urllib.request.Request(
        "http://localhost:{OLLAMA_PORT}/api/generate",
        data=json.dumps(request_data).encode('utf-8'),
        headers={{"Content-Type": "application/json"}},
        method="POST"
    )
    response = urllib.request.urlopen(req, timeout=300)
    result = json.loads(response.read().decode('utf-8'))
    elapsed = time.time() - start_time
    
    # Extrai métricas
    output = result.get('response', '')
    eval_count = result.get('eval_count', 0)
    tokens_per_second = eval_count / elapsed if elapsed > 0 else 0
    
    print(f"LATENCY:{{elapsed:.2f}}")
    print(f"TOKENS:{{tokens_per_second:.2f}}")
    print(f"OUTPUT_TOKENS:{{eval_count}}")
except Exception as e:
    print(f"ERROR:{{str(e)}}")
"""
        
        cmd = f"python3 -c {json.dumps(python_cmd)}"
        output, code, stderr = run_ssh_command(cmd)
        
        if code == 0 and output:
            lines = output.split('\n')
            for line in lines:
                if line.startswith("LATENCY:"):
                    try:
                        latency = float(line.split(":")[1])
                        latencies.append(latency)
                        print(f"  [{i+1}/{num_samples}] Latência: {latency:.2f}s", end="")
                    except:
                        pass
                elif line.startswith("TOKENS:"):
                    try:
                        tps = float(line.split(":")[1])
                        tokens_per_sec.append(tps)
                        print(f" | {tps:.1f} tokens/s")
                    except:
                        pass
                elif line.startswith("OUTPUT_TOKENS:"):
                    try:
                        token_count = int(line.split(":")[1])
                        print(f"     Tokens de saída: {token_count}")
                    except:
                        pass
                elif line.startswith("ERROR:"):
                    print(f"  [{i+1}/{num_samples}] ❌ {line}")
        else:
            print(f"  [{i+1}/{num_samples}] ❌ Erro: {stderr or output}")
    
    return latencies, tokens_per_sec

def print_latency_stats(latencies, tokens_list, label="Latência"):
    """Imprime estatísticas de latência."""
    if not latencies:
        print(f"❌ Sem dados de latência")
        return
    
    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    stdev_latency = statistics.stdev(latencies) if len(latencies) > 1 else 0
    
    print(f"\n📈 {label}:")
    print(f"   Média:    {avg_latency:.2f}s")
    print(f"   Mediana:  {median_latency:.2f}s")
    print(f"   Mín:      {min_latency:.2f}s")
    print(f"   Máx:      {max_latency:.2f}s")
    print(f"   StdDev:   {stdev_latency:.2f}s")
    
    if tokens_list and len(tokens_list) > 0:
        avg_tps = statistics.mean(tokens_list)
        min_tps = min(tokens_list)
        max_tps = max(tokens_list)
        print(f"\n   Throughput:")
        print(f"     Média:   {avg_tps:.1f} tokens/s")
        print(f"     Mín:     {min_tps:.1f} tokens/s")
        print(f"     Máx:     {max_tps:.1f} tokens/s")

def main():
    print("=" * 70)
    print("🔍 Medindo latência do LLM shared-whatsapp:latest via Ollama")
    print(f"   Host: {HOMELAB_HOST}:{OLLAMA_PORT}")
    print(f"   Modelo: {MODEL_NAME}")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Verifica saúde Ollama
    if not check_ollama_health():
        print("❌ Ollama not available. Tentando iniciar...")
        _, code, _ = run_ssh_command("systemctl --user start ollama 2>/dev/null || sudo systemctl start ollama")
        time.sleep(3)
        if not check_ollama_health():
            sys.exit(1)
    
    # Teste 1: Prompts curtos
    short_latencies, short_tps = test_model_latency(num_samples=3, prompt_type="short")
    if short_latencies:
        print_latency_stats(short_latencies, short_tps, "Teste 1: Prompts Curtos")
    
    # Teste 2: Prompts médios
    print("\n" + "-" * 70)
    medium_latencies, medium_tps = test_model_latency(num_samples=3, prompt_type="medium")
    if medium_latencies:
        print_latency_stats(medium_latencies, medium_tps, "Teste 2: Prompts Médios")
    
    # Teste 3: Prompts longos
    print("\n" + "-" * 70)
    long_latencies, long_tps = test_model_latency(num_samples=2, prompt_type="long")
    if long_latencies:
        print_latency_stats(long_latencies, long_tps, "Teste 3: Prompts Longos")
    
    # Resumo geral
    all_latencies = short_latencies + medium_latencies + long_latencies
    all_tps = short_tps + medium_tps + long_tps
    
    print("\n" + "=" * 70)
    if all_latencies:
        print("📊 RESUMO GERAL")
        print_latency_stats(all_latencies, all_tps, "Todas as Requisições")
    print("=" * 70)
    print("✅ Teste concluído")

if __name__ == "__main__":
    main()
