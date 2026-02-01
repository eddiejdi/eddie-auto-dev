#!/usr/bin/env python3
"""Debug do Ollama API"""

import requests

content = open("/home/homelab/myClaude/eddie-assistant-v2.Modelfile").read()
print("Primeiras 200 chars:")
print(content[:200])
print()

r = requests.post(
    "http://192.168.15.2:11434/api/create",
    json={"name": "test-model", "modelfile": content},
)
print("Status:", r.status_code)
print("Response:", r.text[:1000] if r.text else "vazio")
