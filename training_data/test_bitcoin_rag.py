#!/usr/bin/env python3
"""Teste do RAG Bitcoin"""

import requests

RAG_API = "http://localhost:8001/api/v1"

queries = [
    "O que é Bitcoin?",
    "Como funciona o halving?",
    "O que é Lightning Network?",
    "Quem criou o Bitcoin?",
    "Como funciona mineração?",
]

print("=" * 60)
print("🔍 TESTE DO RAG - CONHECIMENTO BITCOIN")
print("=" * 60)

for q in queries:
    try:
        r = requests.post(
            f"{RAG_API}/rag/search",
            json={"query": q, "n_results": 1, "collection": "bitcoin_knowledge"},
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                content = data["results"][0].get("content", "")[:200]
                print(f"\n✅ Q: {q}")
                print(f"   R: {content}...")
            else:
                print(f"\n⚠️ Q: {q} - Sem resultados")
        else:
            print(f"\n❌ Q: {q} - Status {r.status_code}")
    except Exception as e:
        print(f"\n❌ Q: {q} - Erro: {e}")

print("\n" + "=" * 60)
print("✅ Teste concluído!")
