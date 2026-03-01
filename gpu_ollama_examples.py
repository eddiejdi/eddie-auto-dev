#!/usr/bin/env python3
"""
GPU-Accelerated Model Inference via Ollama
Run models on GTX 1050 GPU from Python
"""

import requests
import time
import json
from typing import Generator

OLLAMA_URL = "http://192.168.15.2:11434"

def list_models() -> list:
    """List available models on GPU Ollama"""
    response = requests.get(f"{OLLAMA_URL}/api/tags")
    if response.status_code == 200:
        data = response.json()
        return [m['name'] for m in data.get('models', [])]
    return []

def generate_text(model: str, prompt: str, stream: bool = False) -> dict | Generator:
    """
    Generate text using GPU-accelerated model
    
    Args:
        model: Model name (e.g., 'qwen2.5-coder:7b')
        prompt: Input prompt
        stream: Stream response or return full response
    
    Returns:
        Response dict or generator of chunks
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }
    
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        stream=stream
    )
    
    if stream:
        def chunk_generator():
            for line in response.iter_lines():
                if line:
                    yield json.loads(line)
        return chunk_generator()
    else:
        return response.json()

def chat(model: str, messages: list, stream: bool = False) -> dict | Generator:
    """
    Chat interface for GPU models
    
    Args:
        model: Model name
        messages: List of message dicts with 'role' and 'content'
        stream: Stream or full response
    
    Returns:
        Response dict or generator
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        stream=stream,
        timeout=300
    )
    
    if stream:
        def chunk_generator():
            for line in response.iter_lines():
                if line:
                    yield json.loads(line)
        return chunk_generator()
    else:
        return response.json()

def get_gpu_status() -> dict:
    """Get GPU metrics from Ollama logs"""
    import subprocess
    try:
        result = subprocess.run(
            ["ssh", "homelab@192.168.15.2", "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            vals = result.stdout.strip().split(',')
            return {
                "memory_used_mb": int(vals[0].strip()),
                "memory_total_mb": int(vals[1].strip()),
                "gpu_utilization_percent": int(vals[2].strip()),
                "temperature_c": int(vals[3].strip())
            }
    except Exception as e:
        print(f"❌ GPU status error: {e}")
    
    return {"error": "Could not fetch GPU status"}

# ============================================================================
# EXAMPLES
# ============================================================================

def example_1_list_models():
    """Example 1: List available GPU-accelerated models"""
    print("📦 Available Models:")
    models = list_models()
    for model in models:
        print(f"  • {model}")
    return models

def example_2_simple_generation():
    """Example 2: Simple text generation on GPU"""
    print("\n🚀 Text Generation (GPU Accelerated):")
    
    response = generate_text(
        model="qwen2.5-coder:7b",
        prompt="Write a Python function to calculate Fibonacci numbers",
        stream=False
    )
    
    print(f"Prompt tokens: {response.get('prompt_eval_count', 0)}")
    print(f"Response tokens: {response.get('eval_count', 0)}")
    print(f"Response:\n{response.get('response', '')}")
    
    return response

def example_3_streaming():
    """Example 3: Streaming generation (real-time GPU inference)"""
    print("\n⚡ Streaming Generation:")
    
    for chunk in generate_text(
        model="qwen2.5-coder:7b",
        prompt="Explain GPUs in 3 sentences",
        stream=True
    ):
        if 'response' in chunk:
            print(chunk['response'], end='', flush=True)
    print()

def example_4_chat():
    """Example 4: Chat interface on GPU"""
    print("\n💬 Chat Interface:")
    
    messages = [
        {"role": "user", "content": "What is machine learning?"},
    ]
    
    response = chat("qwen2.5-coder:7b", messages, stream=False)
    
    if 'message' in response:
        print(f"Assistant: {response['message']['content']}")
    else:
        print(f"Error: {response}")
    
    return response

def example_5_gpu_monitoring():
    """Example 5: Monitor GPU while running inference"""
    print("\n📊 GPU Monitoring:")
    
    print("Before inference:")
    before = get_gpu_status()
    print(f"  Memory: {before.get('memory_used_mb', 0)}/{before.get('memory_total_mb', 0)} MB")
    print(f"  GPU Util: {before.get('gpu_utilization_percent', 0)}%")
    print(f"  Temp: {before.get('temperature_c', 0)}°C")
    
    # Run inference
    print("\nRunning inference on GPU...")
    response = generate_text(
        model="qwen2.5-coder:7b",
        prompt="Explain quantum computing in detail",
        stream=False
    )
    
    print("\nAfter inference:")
    after = get_gpu_status()
    print(f"  Memory: {after.get('memory_used_mb', 0)}/{after.get('memory_total_mb', 0)} MB")
    print(f"  GPU Util: {after.get('gpu_utilization_percent', 0)}%")
    print(f"  Temp: {after.get('temperature_c', 0)}°C")
    
    return before, after

if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🎮 GPU-Accelerated Model Inference Examples         ║")
    print("║  NVIDIA GTX 1050 + Ollama                            ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    try:
        # Run examples
        example_1_list_models()
        print("\n" + "="*60)
        
        example_2_simple_generation()
        print("\n" + "="*60)
        
        example_3_streaming()
        print("\n" + "="*60)
        
        example_4_chat()
        print("\n" + "="*60)
        
        example_5_gpu_monitoring()
        
        print("\n✅ All examples completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to Ollama at http://192.168.15.2:11434")
        print("   Make sure the homelab is online and Ollama is running.")
    except Exception as e:
        print(f"❌ Error: {e}")
