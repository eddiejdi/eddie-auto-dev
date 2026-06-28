"""
Shared memory layer for homelab agents.

Uses ChromaDB (v1.4+) with ONNX MiniLM-L6-v2 embeddings (no external API needed).
Embeddings run locally via ONNX — first run downloads ~79 MB model to cache.

Collection: agent_memory
Env var: CHROMA_DB_PATH (default: /home/homelab/myClaude/chroma_db)

Sources convencionados:
    git     — commits do git (git_ingestor)
    wiki    — páginas do Wiki.js
    journal — ações do Action Journal (journal_ingestor)
    alert   — alertas do Grafana/AlertManager
    agent   — fatos armazenados diretamente por agentes
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any

CHROMA_DB_PATH  = os.environ.get("CHROMA_DB_PATH", "/home/homelab/myClaude/chroma_db")
COLLECTION_NAME = "agent_memory"

# Lazy singletons — inicializados na primeira chamada
_client:     Any = None
_collection: Any = None


def _col():
    global _client, _collection
    if _collection is None:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=DefaultEmbeddingFunction(),
            # Cosine distance: valores entre 0 e 2 para vetores normalizados
            # score = (2 - distance) / 2 → 0.0 a 1.0
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── API pública ───────────────────────────────────────────────────────────

def store(
    fact: str,
    source: str = "agent",
    tags: list[str] | None = None,
    agent_id: str | None = None,
    ttl_days: int = 0,
) -> str:
    """Persiste um fato na memória compartilhada. Retorna o memory_id."""
    doc_id = "mem_" + hashlib.sha256(f"{source}:{fact}".encode()).hexdigest()[:12]
    now = int(time.time())
    meta: dict[str, Any] = {
        "source":     source,
        "agent_id":   agent_id or "unknown",
        "tags":       ",".join(tags or []),
        "stored_at":  now,
        "expires_at": (now + ttl_days * 86400) if ttl_days else 0,
    }
    _col().upsert(ids=[doc_id], documents=[fact], metadatas=[meta])
    return doc_id


def search(
    query: str,
    sources: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Busca semântica por similaridade de embedding.

    Retorna lista de {fact, source, agent_id, tags, stored_at, score}.
    score: 0–1, quanto maior mais relevante.
    """
    col   = _col()
    total = col.count()
    if total == 0:
        return []

    n = min(limit, total)
    kwargs: dict[str, Any] = {"query_texts": [query], "n_results": n}
    if sources:
        if len(sources) == 1:
            kwargs["where"] = {"source": {"$eq": sources[0]}}
        else:
            kwargs["where"] = {"$or": [{"source": {"$eq": s}} for s in sources]}

    results = col.query(**kwargs)
    now     = int(time.time())
    out: list[dict[str, Any]] = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        exp  = meta.get("expires_at", 0)
        if exp and exp < now:
            continue
        out.append({
            "fact":       doc,
            "source":     meta.get("source", ""),
            "agent_id":   meta.get("agent_id", ""),
            "tags":       [t for t in meta.get("tags", "").split(",") if t],
            "stored_at":  meta.get("stored_at", 0),
            # Cosine distance ∈ [0,2] → score ∈ [0,1]
            "score":      round((2.0 - float(results["distances"][0][i])) / 2.0, 4),
        })
    return out


def list_recent(
    source: str | None = None,
    agent_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Lista memórias recentes (sem busca semântica).

    Útil para ingestores verificarem o que já foi indexado.
    """
    col   = _col()
    total = col.count()
    if total == 0:
        return []

    where: dict | None = None
    if source and agent_id:
        where = {"$and": [{"source": {"$eq": source}}, {"agent_id": {"$eq": agent_id}}]}
    elif source:
        where = {"source": {"$eq": source}}
    elif agent_id:
        where = {"agent_id": {"$eq": agent_id}}

    kwargs: dict[str, Any] = {"limit": min(limit, total)}
    if where:
        kwargs["where"] = where

    results = col.get(**kwargs)
    now = int(time.time())
    out: list[dict[str, Any]] = []
    for i, doc in enumerate(results["documents"]):
        meta = results["metadatas"][i]
        exp  = meta.get("expires_at", 0)
        if exp and exp < now:
            continue
        out.append({
            "fact":      doc,
            "source":    meta.get("source", ""),
            "agent_id":  meta.get("agent_id", ""),
            "tags":      [t for t in meta.get("tags", "").split(",") if t],
            "stored_at": meta.get("stored_at", 0),
        })

    out.sort(key=lambda x: x["stored_at"], reverse=True)
    return out[:limit]


def count(source: str | None = None) -> int:
    """Retorna o número de memórias (por source ou total)."""
    col = _col()
    if not source:
        return col.count()
    results = col.get(where={"source": {"$eq": source}})
    return len(results["ids"])
