#!/usr/bin/env python3
"""
Mede o tempo de resposta do LLM do container eddie-whatsapp:latest no homelab.
Testa por SSH, descobrindo automaticamente a porta e tipo de API.
"""

import subprocess
import json
import re
import statistics
import time
import sys
from datetime import datetime

HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
CONTAINER_NAME = "eddie-whatsapp"

def run_ssh_command(cmd):
    """Executa comando via SSH no homelab."""
    try:
        result = subprocess.run(
            ["ssh", f"{HOMELAB_USER}@{HOMELAB_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        print(f"❌ Erro SSH: {e}")
        return None, -1

def check_container_running():
    """Verifica se o container está rodando."""
    cmd = f"docker ps --filter 'name={CONTAINER_NAME}' --format '{{{{.Status}}}}'"
    output, code = run_ssh_command(cmd)
    if code == 0 and output:
        print(f"✓ Container status: {output}")
        return "Up" in output
    print("❌ Container não encontrado ou não está rodando")
    return False

def discover_api_port():
    """Descobre a porta da API do container."""
    cmd = f"docker port {CONTAINER_NAME} 2>/dev/null | grep -E ':[0-9]+' | head -1"
    output, code = run_ssh_command(cmd)
    
    if code == 0 and output:
        # Format: "8000/tcp -> 0.0.0.0:8000" ou "8000/tcp -> 127.0.0.1:8000"
        match = re.search(r':(\d+)', output)
        if match:
            port = match.group(1)
            print(f"✓ API descoberta na porta: {port}")
            return int(port)
    
    print("⚠ Não foi possível descobrir a porta. Testando portas comuns...")
    for port in [8000, 8080, 5000, 3000, 11434]:
        cmd = f"docker exec {CONTAINER_NAME} sh -c 'curl -s http://localhost:{port}/health >/dev/null 2>&1' && echo 'FOUND'"
        output, code = run_ssh_command(cmd)
        if code == 0 and "FOUND" in output:
            print(f"✓ Porta funcional encontrada: {port}")
            return port
    
    return None

def test_ollama_latency(port, num_samples=5, prompt_length="short"):
    """Testa latência de um endpoint Ollama-compatível."""
    prompts = {
        "short": "Olá, como você está?",
        "medium": "Explique em uma frase o que é inteligência artificial.",
        "long": "Descreva em detalhes os primeiros 30 anos de história da internet e seu impacto na sociedade moderna."
    }
    
    prompt = prompts.get(prompt_length, prompts["short"])
    
    print(f"\n📊 Testando {num_samples} requisições (prompt: '{prompt[:50]}...')")
    
    latencies = []
    
    for i in range(num_samples):
        cmd = f"""
docker exec {CONTAINER_NAME} sh -c '
import json
import time
import urllib.request
import urllib.error

start = time.time()
try:
    request = urllib.request.Request(
        "http://localhost:{port}/api/generate",
        method="POST",
        data=json.dumps({{"model": "mistral", "prompt": "{prompt}", "stream": False}}).encode(),
        headers={{"Content-Type": "application/json"}}
    )
    response = urllib.request.urlopen(request, timeout=120)
    elapsed = time.time() - start
    print(f"{{elapsed:.2f}}")
except urllib.error.URLError as e:
    print(f"ERROR: {{e}}")
except Exception as e:
    print(f"ERROR: {{str(e)}}")
' python3
"""
        output, code = run_ssh_command(cmd)
        
        if code == 0 and output and "ERROR" not in output:
            try:
                latency = float(output.split()[0])
                latencies.append(latency)
                print(f"  [{i+1}/{num_samples}] {latency:.2f}s")
            except:
                print(f"  [{i+1}/{num_samples}] ⚠ Falha parsing: {output}")
        else:
            print(f"  [{i+1}/{num_samples}] ❌ Erro: {output}")
    
    return latencies

def test_http_latency(port, endpoint="/health", num_samples=5):
    """Testa latência de um endpoint HTTP simples."""
    print(f"\n📊 Testando {num_samples} requisições HTTP ({endpoint})")
    
    latencies = []
    
    for i in range(num_samples):
        cmd = f"""
docker exec {CONTAINER_NAME} sh -c '
import time
import urllib.request
import urllib.error

start = time.time()
try:
    urllib.request.urlopen("http://localhost:{port}{endpoint}", timeout=30)
    elapsed = time.time() - start
    print(f"{{elapsed*1000:.0f}}")
except Exception as e:
    print(f"ERROR: {{e}}")
' python3
"""
        output, code = run_ssh_command(cmd)
        
        if code == 0 and output and "ERROR" not in output:
            try:
                latency_ms = float(output.split()[0])
                latencies.append(latency_ms)
                print(f"  [{i+1}/{num_samples}] {latency_ms:.0f}ms")
            except:
                print(f"  [{i+1}/{num_samples}] ⚠ Falha parsing: {output}")
        else:
            print(f"  [{i+1}/{num_samples}] ❌ Erro: {output}")
    
    return latencies

def print_latency_stats(latencies, label="Latência", unit="s"):
    """Imprime estatísticas de latência."""
    if not latencies:
        print(f"❌ Sem dados de latência")
        return
    
    avg = statistics.mean(latencies)
    median = statistics.median(latencies)
    min_val = min(latencies)
    max_val = max(latencies)
    stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0
    
    print(f"\n📈 {label}:")
    print(f"   Média:    {avg:.2f}{unit}")
    print(f"   Mediana:  {median:.2f}{unit}")
    print(f"   Mín:      {min_val:.2f}{unit}")
    print(f"   Máx:      {max_val:.2f}{unit}")
    print(f"   StdDev:   {stdev:.2f}{unit}")

def main():
    print("=" * 60)
    print("🔍 Medindo latência do LLM eddie-whatsapp:latest")
    print(f"   Host: {HOMELAB_HOST}")
    print(f"   Container: {CONTAINER_NAME}")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Verifica se container está rodando
    if not check_container_running():
        sys.exit(1)
    
    # Descobre porta API
    port = discover_api_port()
    if not port:
        print("❌ Não foi possível descobrir a porta da API")
        sys.exit(1)
    
    # Testa endpoints
    print("\n🔄 Tentando diferentes tipos de teste...")
    
    # Teste 1: Health check (HTTP simples)
    http_latencies = test_http_latency(port, "/health", num_samples=3)
    if http_latencies:
        print_latency_stats(http_latencies, "HTTP /health", "ms")
    
    # Teste 2: Ollama API (LLM)
    print("\n🤖 Testando LLM (Ollama API)...")
    ollama_latencies = test_ollama_latency(port, num_samples=3, prompt_length="short")
    if ollama_latencies:
        print_latency_stats(ollama_latencies, "LLM (geração completa)", "s")
    else:
        print("⚠ LLM não respondeu. Pode não ser Ollama ou estar não configurado.")
    
    print("\n" + "=" * 60)
    print("✅ Teste concluído")
    print("=" * 60)

if __name__ == "__main__":
    main()
