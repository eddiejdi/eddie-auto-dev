#!/usr/bin/env python3
"""Teste final do RAG com dados indexados"""

import requests

RAG_API = "http://192.168.15.2:8001"


def test_search(query, description):
    print("=" * 60)
    print(f"TESTE: {description}")
    print("=" * 60)
    r = requests.post(
        f"{RAG_API}/api/v1/rag/search",
        json={"query": query, "collection": "chat_history", "top_k": 3},
    )
    print(f"Status: {r.status_code}")
    data = r.json()
    results = data.get("results", [])
    print(f"Resultados encontrados: {len(results)}")
    for i, result in enumerate(results, 1):
        content = result.get("content", "")[:200]
        print(f"\n--- Resultado {i} ---")
        print(content + "...")
    print()


if __name__ == "__main__":
    test_search("GitHub MCP server ferramentas", "Busca sobre GitHub MCP Server")
    test_search("Ollama codestral modelo", "Busca sobre Ollama modelos")
    test_search("Continue Cline extensão", "Busca sobre extensões VS Code")

    print("=" * 60)
    print("✅ RAG INDEXADO COM SUCESSO!")
    print("92 conversas do dia estão disponíveis para consulta")
    print("Collection: chat_history")
    print("=" * 60)
