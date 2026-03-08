#!/usr/bin/env python3
"""Teste Rápido: Qwen Image Agent"""

import sys
sys.path.insert(0, '/home/edenilson/shared-auto-dev')

print("\n" + "="*70)
print(" "*15 + "QWEN IMAGE AGENT - TESTE DE INTEGRAÇÃO")
print("="*70)

# Test 1
print("\n[1/5] Verificando imports base...")
try:
    import torch
    import httpx
    print("  ✓ torch, httpx")
except ImportError as e:
    print(f"  ✗ Erro: {e}")
    sys.exit(1)

# Test 2
print("\n[2/5] Verificando diffusers...")
try:
    from diffusers import StableDiffusionPipeline
    print("  ✓ diffusers.StableDiffusionPipeline")
except ImportError as e:
    print(f"  ✗ Erro: {e}")
    sys.exit(1)

# Test 3
print("\n[3/5] Agent Communication Bus...")
try:
    from specialized_agents.agent_communication_bus import AgentCommunicationBus, MessageType
    bus = AgentCommunicationBus()
    print(f"  ✓ Bus inicializado")
    print(f"    - Status: {'recording' if bus.recording else 'paused'}")
except Exception as e:
    print(f"  ✗ Erro: {e}")
    sys.exit(1)

# Test 4
print("\n[4/5] QwenImageAgent...")
try:
    from specialized_agents.qwen_image_agent import QwenImageAgent
    agent = QwenImageAgent(device="cpu")
    print(f"  ✓ Agent criado: {agent.agent_id}")
    print(f"    - Cache: {agent.cache_dir}")
except Exception as e:
    print(f"  ✗ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5
print("\n[5/5] QwenImageClient...")
try:
    from specialized_agents.qwen_image_client import QwenImageClient
    client = QwenImageClient(client_id="test-client")
    print(f"  ✓ Client criado: {client.client_id}")
except Exception as e:
    print(f"  ✗ Erro: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("✅ TODOS OS TESTES PASSARAM!")
print("="*70)

print("\n📊 Resumo:")
print("  ✓ Imports base (torch, httpx, diffusers)")
print("  ✓ Agent Communication Bus")
print("  ✓ QwenImageAgent (class: OK, instance: OK)")
print("  ✓ QwenImageClient (class: OK, instance: OK)")

print("\n🚀 Próximos passos:")
print("  1. Iniciar agent: python -m specialized_agents.qwen_image_agent")
print("  2. Enviar requisição: python specialized_agents/qwen_image_client.py simple")
print("  3. Verificar imagens: ls ~/agent_data/image_cache/")

print("\n" + "="*70 + "\n")

sys.exit(0)
