#!/usr/bin/env python3
"""Teste de busca no RAG"""

import requests
import chromadb
from pathlib import Path

CHROMA_DIR = Path(__file__).parent / "chroma_db"
OLLAMA_URL = "http://192.168.15.2:11434"


def get_embedding(text):
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    return resp.json()["embedding"] if resp.status_code == 200 else None


def search_rag(query, n_results=3):
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection("eddie_knowledge_v2")

    embedding = get_embedding(query)
    if not embedding:
        return []

    results = collection.query(query_embeddings=[embedding], n_results=n_results)
    return results


# Teste
queries = [
    "Como configurar WhatsApp?",
    "Qual modelo usar para assistente?",
    "Comandos do Ollama",
]

for q in queries:
    print(f"\n🔍 Query: {q}")
    print("-" * 40)
    results = search_rag(q)
    for i, doc in enumerate(results["documents"][0]):
        print(f"  {i + 1}. {doc[:100]}...")
