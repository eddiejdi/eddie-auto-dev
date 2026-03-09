#!/usr/bin/env python3
"""Diagnóstico de GPUs Ollama e calibração de modelos.

Script para testar conectividade, performance e carga de modelos em GPU0 e GPU1.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Tuple

OLLAMA_GPU0 = "http://192.168.15.2:11434"
OLLAMA_GPU1 = "http://192.168.15.2:11435"

def test_connectivity(host: str, name: str) -> bool:
    """Testa se host Ollama está acessível."""
    try:
        req_data = json.dumps({
            "model": "llama2",
            "prompt": "test",
            "stream": False,
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        
        with urllib.request.urlopen(req, timeout=3) as resp:
            _ = resp.read()
            print(f"✓ {name} ({host}) — CONECTADO")
            return True
    except urllib.error.URLError as e:
        print(f"✗ {name} ({host}) — ERRO: {e.reason}")
        return False
    except Exception as e:
        print(f"✗ {name} ({host}) — TIMEOUT/ERRO: {e}")
        return False

def list_models(host: str, name: str) -> list:
    """Lista modelos carregados em uma GPU."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
            models = data.get("models", [])
            if models:
                print(f"\n📦 Modelos em {name}:")
                for m in models:
                    mname = m.get("name", "?")
                    size = m.get("size", 0) / (1024**3)
                    print(f"  - {mname} ({size:.1f}GB)")
                return models
            else:
                print(f"⚠ {name} — nenhum modelo carregado")
                return []
    except Exception as e:
        print(f"⚠ {name} — erro ao listar modelos: {e}")
        return []

def test_inference(host: str, model: str, prompt: str, timeout: int = 10) -> Tuple[bool, float]:
    """Testa inferência e mede tempo."""
    try:
        start = time.time()
        req_data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 32,
                "temperature": 0.1,
            },
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            elapsed = time.time() - start
            return True, elapsed
    except Exception as e:
        print(f"     Erro: {e}")
        return False, 0.0

def main() -> None:
    """Main diagnostics."""
    print("=" * 70)
    print("DIAGNÓSTICO OLLAMA — GPU0 vs GPU1")
    print("=" * 70)
    
    # Fase 1: Conectividade
    print("\n[1] TESTE DE CONECTIVIDADE")
    print("-" * 70)
    gpu0_ok = test_connectivity(OLLAMA_GPU0, "GPU0 (RTX 2060)")
    gpu1_ok = test_connectivity(OLLAMA_GPU1, "GPU1 (GTX 1050)")
    
    if not gpu0_ok and not gpu1_ok:
        print("\n❌ NENHUMA GPU ACESSÍVEL!")
        sys.exit(1)
    
    # Fase 2: Modelos carregados
    print("\n[2] MODELOS CARREGADOS")
    print("-" * 70)
    models_gpu0 = list_models(OLLAMA_GPU0, "GPU0") if gpu0_ok else []
    models_gpu1 = list_models(OLLAMA_GPU1, "GPU1") if gpu1_ok else []
    
    # Fase 3: Teste de performance
    print("\n[3] TESTE DE PERFORMANCE")
    print("-" * 70)
    
    test_prompts = [
        ("short", "hello", 5),
        ("medium", "Can you explain what is Bitcoin in one sentence?", 10),
        ("long", "What are the top 5 risks in cryptocurrency trading and how do traders mitigate them? Provide detailed analysis.", 20),
    ]
    
    for test_name, prompt, timeout_sec in test_prompts:
        print(f"\n🧪 Teste: {test_name.upper()} (timeout={timeout_sec}s)")
        print(f"   Prompt: {prompt[:60]}...")
        
        models_to_test = []
        if gpu0_ok and models_gpu0:
            models_to_test.append((OLLAMA_GPU0, "GPU0", models_gpu0[0]["name"]))
        if gpu1_ok and models_gpu1:
            models_to_test.append((OLLAMA_GPU1, "GPU1", models_gpu1[0]["name"]))
        
        if not models_to_test:
            # Tentar modelos genéricos
            if gpu0_ok:
                models_to_test.append((OLLAMA_GPU0, "GPU0", "llama2"))
            if gpu1_ok:
                models_to_test.append((OLLAMA_GPU1, "GPU1", "llama2"))
        
        for host, gpu_name, model in models_to_test:
            print(f"   > {gpu_name} + {model}...", end=" ", flush=True)
            success, elapsed = test_inference(host, model, prompt, timeout=timeout_sec)
            if success:
                print(f"✓ {elapsed:.2f}s")
            else:
                print(f"✗ TIMEOUT/ERRO")
    
    # Fase 4: Recomendações
    print("\n[4] RECOMENDAÇÕES")
    print("-" * 70)
    
    if not gpu0_ok and not gpu1_ok:
        print("❌ Nenhuma GPU está acessível. Verifique:")
        print("   1. Ollama está rodando em ambas as máquinas?")
        print("   2. Network 192.168.15.x está ok?")
        print("   3. Portas 11434 e 11435 estão abertas?")
    elif gpu0_ok and not gpu1_ok:
        print("⚠ Apenas GPU0 (RTX 2060) está acessível.")
        print("  → Use GPU0 para todas as operações.")
    elif gpu1_ok and not gpu0_ok:
        print("⚠ Apenas GPU1 (GTX 1050) está acessível.")
        print("  → Use GPU1 para todas as operações.")
    else:
        print("✓ Ambas as GPUs estão acessíveis.")
        print("  → Balancear carga: luz (CPU/GPU1), pesado (GPU0)")
        print("  → Sentinel: se GPU1 timeout, fallback para GPU0")
    
    print("\n[5] PRÓXIMOS PASSOS")
    print("-" * 70)
    print("1. Carregar modelo de sentimento:")
    print("   ollama pull qwen2.5-coder:7b")
    print("2. Iniciar RSS Sentiment Exporter:")
    print("   sudo systemctl start rss-sentiment-exporter")
    print("3. Monitorar logs:")
    print("   journalctl -u rss-sentiment-exporter -f")
    print("=" * 70)


if __name__ == "__main__":
    main()
