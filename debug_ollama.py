#!/usr/bin/env python3
"""Debug do Ollama API"""

import json
import os
import requests

content = open("/home/homelab/myClaude/eddie-assistant-v2.Modelfile").read()
print("Primeiras 200 chars:")
print(content[:200])
print()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

r = requests.post(
    f"{OLLAMA_HOST}/api/create",
    json={"name": "test-model", "modelfile": content}
)
print("Status:", r.status_code)
print("Response:", r.text[:1000] if r.text else "vazio")
