#!/usr/bin/env python3
import httpx

response = httpx.post(
    "http://192.168.15.2:11434/api/show", json={"name": "eddie-coder"}
)

data = response.json()
print("=== System Prompt ===")
print(data.get("system", "Sem system prompt"))
print("\n=== Template ===")
print(data.get("template", "Sem template")[:500])
print("\n=== Parameters ===")
print(data.get("parameters", "Sem parameters"))
