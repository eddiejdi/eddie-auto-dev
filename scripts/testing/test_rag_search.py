#!/usr/bin/env python3
"""Teste de busca no RAG."""

import requests
import json

RAG_API = "http://localhost:8001"

payload = {
    "query": "como acessar o ollama pela internet",
    "collection": "homelab",
    "n_results": 3
}

response = requests.post(f"{RAG_API}/api/v1/rag/search", json=payload)
print(f"Status: {response.status_code}")
result = response.json()
print(f"Total encontrado: {result.get('total_found', 0)}")
print()
for i, doc in enumerate(result.get('results', []), 1):
    print(f"--- Resultado {i} ---")
    print(f"Score: {doc.get('score', 'N/A')}")
    print(f"Source: {doc.get('metadata', {}).get('source', 'N/A')}")
    print(f"Content preview: {doc.get('content', '')[:200]}...")
    print()
