#!/usr/bin/env python3
import os
import httpx
import json

OLLAMA_URL = os.environ.get('OLLAMA_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

response = httpx.post(
    f"{OLLAMA_URL}/api/show",
    json={"name": "eddie-coder"}
)

data = response.json()
print("=== System Prompt ===")
print(data.get("system", "Sem system prompt"))
print("\n=== Template ===")
print(data.get("template", "Sem template")[:500])
print("\n=== Parameters ===")
print(data.get("parameters", "Sem parameters"))
