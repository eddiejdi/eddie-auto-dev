"""
OpenSearch Agent — Agente especializado em OpenSearch
Integra busca semântica, indexação de código, logs e observabilidade
com o homelab e modelos LLM (Ollama).

Funcionalidades:
- Indexação e busca full-text de código dos agentes
- Busca vetorial/semântica (k-NN) para RAG
- Ingestão de logs de agentes e serviços
- Observabilidade e analytics
- Integração com Ollama para embeddings e enriquecimento
"""
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# Configurações
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "192.168.15.2")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_USE_SSL = os.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true"
OPENSEARCH_VERIFY_CERTS = os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
EMBEDDING_MODEL = os.getenv("OPENSEARCH_EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIM = int(os.getenv("OPENSEARCH_EMBEDDING_DIM", "768"))

# Índices padrão
INDEX_CODE = "eddie-code"
INDEX_LOGS = "eddie-logs"
INDEX_DOCS = "eddie-docs"
INDEX_CONVERSATIONS = "eddie-conversations"
INDEX_RAG = "eddie-rag-vectors"

# Import do bus de comunicação (opcional)
try:
    from .agent_communication_bus import (
        get_communication_bus,
        log_request,
        log_response,
        log_error,
        log_task_start,
        log_task_end,
        MessageType,
    )
    COMM_BUS_AVAILABLE = True
except ImportError:
    COMM_BUS_AVAILABLE = False


class OpenSearchAgent:
    """
    Agente OpenSearch para o Eddie Auto-Dev.
    Gerencia índices, busca semântica, ingestão de logs e integração com LLMs.
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        use_ssl: bool = None,
    ):
        self.host = host or OPENSEARCH_HOST
        self.port = port or OPENSEARCH_PORT
        self.user = user or OPENSEARCH_USER
        self.password = password or OPENSEARCH_PASSWORD
        self.use_ssl = use_ssl if use_ssl is not None else OPENSEARCH_USE_SSL
        self.scheme = "https" if self.use_ssl else "http"
        self.base_url = f"{self.scheme}://{self.host}:{self.port}"

        # HTTP client
        auth = (self.user, self.password) if self.password else None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            verify=OPENSEARCH_VERIFY_CERTS,
            timeout=30.0,
        )

        # Ollama client para embeddings
        self._ollama = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=60.0)

        # Métricas
        self._metrics = {
            "requests_total": 0,
            "index_operations": 0,
            "search_operations": 0,
            "errors_total": 0,
            "embedding_calls": 0,
            "last_activity": None,
        }

    # ──────────── Lifecycle ────────────

    async def close(self):
        """Fecha conexões HTTP."""
        await self._client.aclose()
        await self._ollama.aclose()

    # ──────────── Health / Info ────────────

    async def health(self) -> Dict[str, Any]:
        """Verifica saúde do cluster OpenSearch."""
        self._metrics["requests_total"] += 1
        try:
            resp = await self._client.get("/_cluster/health")
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": data.get("status", "unknown"),
                "cluster_name": data.get("cluster_name"),
                "number_of_nodes": data.get("number_of_nodes"),
                "active_shards": data.get("active_shards"),
                "unassigned_shards": data.get("unassigned_shards"),
                "connected": True,
            }
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"status": "unreachable", "connected": False, "error": str(e)}

    async def cluster_info(self) -> Dict[str, Any]:
        """Retorna informações do cluster."""
        self._metrics["requests_total"] += 1
        try:
            resp = await self._client.get("/")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"error": str(e)}

    async def list_indices(self) -> List[Dict[str, Any]]:
        """Lista todos os índices."""
        self._metrics["requests_total"] += 1
        try:
            resp = await self._client.get("/_cat/indices?format=json")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._metrics["errors_total"] += 1
            return [{"error": str(e)}]

    # ──────────── Embeddings (Ollama) ────────────

    async def generate_embedding(self, text: str, model: str = None) -> List[float]:
        """Gera embedding vetorial usando Ollama."""
        model = model or EMBEDDING_MODEL
        self._metrics["embedding_calls"] += 1
        try:
            resp = await self._ollama.post(
                "/api/embed",
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama retorna {"embeddings": [[...]], ...}
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
            # Fallback formato antigo
            return data.get("embedding", [])
        except Exception as e:
            self._metrics["errors_total"] += 1
            if COMM_BUS_AVAILABLE:
                log_error("opensearch_agent", f"Embedding error: {e}")
            return []

    async def generate_embeddings_batch(
        self, texts: List[str], model: str = None
    ) -> List[List[float]]:
        """Gera embeddings em batch."""
        model = model or EMBEDDING_MODEL
        results = []
        # Processar em chunks de 10
        for i in range(0, len(texts), 10):
            chunk = texts[i : i + 10]
            tasks = [self.generate_embedding(t, model) for t in chunk]
            batch = await asyncio.gather(*tasks, return_exceptions=True)
            for item in batch:
                if isinstance(item, Exception):
                    results.append([])
                else:
                    results.append(item)
        return results

    # ──────────── Index Management ────────────

    async def create_index(
        self,
        index_name: str,
        mappings: Dict = None,
        settings: Dict = None,
    ) -> Dict[str, Any]:
        """Cria um índice no OpenSearch."""
        self._metrics["requests_total"] += 1
        body: Dict[str, Any] = {}
        if settings:
            body["settings"] = settings
        if mappings:
            body["mappings"] = mappings

        try:
            resp = await self._client.put(f"/{index_name}", json=body)
            if resp.status_code == 400 and "already_exists" in resp.text:
                return {"acknowledged": True, "already_exists": True}
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"error": str(e)}

    async def delete_index(self, index_name: str) -> Dict[str, Any]:
        """Remove um índice."""
        self._metrics["requests_total"] += 1
        try:
            resp = await self._client.delete(f"/{index_name}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"error": str(e)}

    async def setup_default_indices(self) -> Dict[str, Any]:
        """Cria todos os índices padrão do Eddie."""
        results = {}

        # Índice de código (full-text + metadata)
        results["code"] = await self.create_index(
            INDEX_CODE,
            settings={"index": {"number_of_shards": 1, "number_of_replicas": 0}},
            mappings={
                "properties": {
                    "language": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "filepath": {"type": "text"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text"},
                    "agent": {"type": "keyword"},
                    "project": {"type": "keyword"},
                    "indexed_at": {"type": "date"},
                    "lines": {"type": "integer"},
                    "size_bytes": {"type": "integer"},
                }
            },
        )

        # Índice de logs (observabilidade)
        results["logs"] = await self.create_index(
            INDEX_LOGS,
            settings={
                "index": {"number_of_shards": 1, "number_of_replicas": 0},
            },
            mappings={
                "properties": {
                    "timestamp": {"type": "date"},
                    "level": {"type": "keyword"},
                    "service": {"type": "keyword"},
                    "agent": {"type": "keyword"},
                    "message": {"type": "text"},
                    "task_id": {"type": "keyword"},
                    "conversation_id": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        )

        # Índice de documentação
        results["docs"] = await self.create_index(
            INDEX_DOCS,
            settings={"index": {"number_of_shards": 1, "number_of_replicas": 0}},
            mappings={
                "properties": {
                    "title": {"type": "text", "analyzer": "standard"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "category": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "source_file": {"type": "keyword"},
                    "indexed_at": {"type": "date"},
                }
            },
        )

        # Índice de conversas (interceptor)
        results["conversations"] = await self.create_index(
            INDEX_CONVERSATIONS,
            settings={"index": {"number_of_shards": 1, "number_of_replicas": 0}},
            mappings={
                "properties": {
                    "conversation_id": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "target": {"type": "keyword"},
                    "phase": {"type": "keyword"},
                    "content": {"type": "text"},
                    "timestamp": {"type": "date"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        )

        # Índice RAG vetorial (k-NN)
        results["rag"] = await self.create_index(
            INDEX_RAG,
            settings={
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "knn": True,
                },
            },
            mappings={
                "properties": {
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": EMBEDDING_DIM,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene",
                            "parameters": {"ef_construction": 128, "m": 16},
                        },
                    },
                    "language": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": True},
                    "indexed_at": {"type": "date"},
                }
            },
        )

        return results

    # ──────────── Indexação ────────────

    async def index_document(
        self, index_name: str, document: Dict, doc_id: str = None
    ) -> Dict[str, Any]:
        """Indexa um documento."""
        self._metrics["index_operations"] += 1
        self._metrics["last_activity"] = datetime.now(timezone.utc).isoformat()
        try:
            if doc_id:
                resp = await self._client.put(
                    f"/{index_name}/_doc/{doc_id}?refresh=true", json=document
                )
            else:
                resp = await self._client.post(
                    f"/{index_name}/_doc?refresh=true", json=document
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"error": str(e)}

    async def bulk_index(
        self, index_name: str, documents: List[Dict], id_field: str = None
    ) -> Dict[str, Any]:
        """Indexa documentos em bulk."""
        self._metrics["index_operations"] += len(documents)
        lines = []
        for doc in documents:
            action = {"index": {"_index": index_name}}
            if id_field and id_field in doc:
                action["index"]["_id"] = str(doc[id_field])
            lines.append(json.dumps(action))
            lines.append(json.dumps(doc))
        body = "\n".join(lines) + "\n"

        try:
            resp = await self._client.post(
                "/_bulk?refresh=true",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "took": data.get("took"),
                "errors": data.get("errors"),
                "items_count": len(data.get("items", [])),
            }
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"error": str(e)}

    # ──────────── Indexação Especializada ────────────

    async def index_code(
        self,
        code: str,
        language: str,
        filename: str,
        filepath: str = "",
        agent: str = "",
        project: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """Indexa um arquivo de código."""
        doc_id = hashlib.sha256(f"{filepath or filename}:{language}".encode()).hexdigest()[:16]
        doc = {
            "language": language,
            "filename": filename,
            "filepath": filepath,
            "content": code,
            "description": description,
            "agent": agent,
            "project": project,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "lines": code.count("\n") + 1,
            "size_bytes": len(code.encode("utf-8")),
        }
        result = await self.index_document(INDEX_CODE, doc, doc_id=doc_id)

        if COMM_BUS_AVAILABLE:
            log_request(
                "opensearch_agent",
                "opensearch",
                {"action": "index_code", "language": language, "file": filename},
            )

        return result

    async def index_log(
        self,
        message: str,
        level: str = "INFO",
        service: str = "",
        agent: str = "",
        task_id: str = "",
        conversation_id: str = "",
        metadata: Dict = None,
    ) -> Dict[str, Any]:
        """Indexa uma entrada de log."""
        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": service,
            "agent": agent,
            "message": message,
            "task_id": task_id,
            "conversation_id": conversation_id,
            "metadata": metadata or {},
        }
        return await self.index_document(INDEX_LOGS, doc)

    async def index_for_rag(
        self,
        text: str,
        language: str = "",
        source: str = "",
        metadata: Dict = None,
        chunk_id: str = None,
    ) -> Dict[str, Any]:
        """Indexa texto com embedding vetorial para RAG."""
        embedding = await self.generate_embedding(text)
        if not embedding:
            return {"error": "Failed to generate embedding"}

        doc_id = chunk_id or hashlib.sha256(text.encode()).hexdigest()[:16]
        doc = {
            "text": text,
            "embedding": embedding,
            "language": language,
            "source": source,
            "chunk_id": doc_id,
            "metadata": metadata or {},
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self.index_document(INDEX_RAG, doc, doc_id=doc_id)

    async def index_doc_content(
        self,
        title: str,
        content: str,
        category: str = "",
        tags: List[str] = None,
        source_file: str = "",
    ) -> Dict[str, Any]:
        """Indexa documentação do projeto."""
        doc_id = hashlib.sha256(f"{title}:{source_file}".encode()).hexdigest()[:16]
        doc = {
            "title": title,
            "content": content,
            "category": category,
            "tags": tags or [],
            "source_file": source_file,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self.index_document(INDEX_DOCS, doc, doc_id=doc_id)

    # ──────────── Busca ────────────

    async def search(
        self,
        index_name: str,
        query: Dict,
        size: int = 10,
        source_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Executa busca genérica."""
        self._metrics["search_operations"] += 1
        self._metrics["last_activity"] = datetime.now(timezone.utc).isoformat()
        body: Dict[str, Any] = {"size": size, "query": query}
        if source_fields:
            body["_source"] = source_fields

        try:
            resp = await self._client.post(f"/{index_name}/_search", json=body)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {})
            return {
                "total": hits.get("total", {}).get("value", 0),
                "hits": [
                    {
                        "_id": h["_id"],
                        "_score": h.get("_score"),
                        **h.get("_source", {}),
                    }
                    for h in hits.get("hits", [])
                ],
                "took_ms": data.get("took", 0),
            }
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"total": 0, "hits": [], "error": str(e)}

    async def search_code(
        self,
        query_text: str,
        language: str = None,
        size: int = 10,
    ) -> Dict[str, Any]:
        """Busca full-text em código indexado."""
        must_clauses: List[Dict] = [
            {
                "multi_match": {
                    "query": query_text,
                    "fields": ["content^2", "description", "filename"],
                }
            }
        ]
        if language:
            must_clauses.append({"term": {"language": language}})

        return await self.search(
            INDEX_CODE,
            {"bool": {"must": must_clauses}},
            size=size,
            source_fields=["language", "filename", "filepath", "description", "lines", "agent"],
        )

    async def search_logs(
        self,
        query_text: str = None,
        level: str = None,
        service: str = None,
        agent: str = None,
        since: str = None,
        size: int = 50,
    ) -> Dict[str, Any]:
        """Busca em logs indexados."""
        must_clauses: List[Dict] = []
        if query_text:
            must_clauses.append({"match": {"message": query_text}})
        if level:
            must_clauses.append({"term": {"level": level}})
        if service:
            must_clauses.append({"term": {"service": service}})
        if agent:
            must_clauses.append({"term": {"agent": agent}})
        if since:
            must_clauses.append({"range": {"timestamp": {"gte": since}}})

        if not must_clauses:
            must_clauses.append({"match_all": {}})

        return await self.search(
            INDEX_LOGS,
            {"bool": {"must": must_clauses}},
            size=size,
        )

    async def search_docs(
        self,
        query_text: str,
        category: str = None,
        size: int = 10,
    ) -> Dict[str, Any]:
        """Busca em documentação indexada."""
        must_clauses: List[Dict] = [
            {
                "multi_match": {
                    "query": query_text,
                    "fields": ["title^3", "content", "tags^2"],
                }
            }
        ]
        if category:
            must_clauses.append({"term": {"category": category}})

        return await self.search(INDEX_DOCS, {"bool": {"must": must_clauses}}, size=size)

    async def semantic_search(
        self,
        query_text: str,
        language: str = None,
        size: int = 5,
        min_score: float = 0.5,
    ) -> Dict[str, Any]:
        """Busca semântica via k-NN (vetorial) para RAG."""
        embedding = await self.generate_embedding(query_text)
        if not embedding:
            return {"total": 0, "hits": [], "error": "Failed to generate embedding"}

        knn_query: Dict[str, Any] = {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": size,
                }
            }
        }

        # Filtro por linguagem se necessário
        filter_clause = None
        if language:
            filter_clause = [{"term": {"language": language}}]

        body: Dict[str, Any] = {
            "size": size,
            "query": knn_query,
            "min_score": min_score,
        }
        if filter_clause:
            body["query"] = {
                "bool": {
                    "must": [knn_query],
                    "filter": filter_clause,
                }
            }

        self._metrics["search_operations"] += 1
        try:
            resp = await self._client.post(f"/{INDEX_RAG}/_search", json=body)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {})
            return {
                "total": hits.get("total", {}).get("value", 0),
                "hits": [
                    {
                        "_id": h["_id"],
                        "_score": h.get("_score"),
                        "text": h.get("_source", {}).get("text", ""),
                        "language": h.get("_source", {}).get("language", ""),
                        "source": h.get("_source", {}).get("source", ""),
                        "metadata": h.get("_source", {}).get("metadata", {}),
                    }
                    for h in hits.get("hits", [])
                ],
                "took_ms": data.get("took", 0),
            }
        except Exception as e:
            self._metrics["errors_total"] += 1
            return {"total": 0, "hits": [], "error": str(e)}

    # ──────────── RAG Pipeline ────────────

    async def rag_query(
        self,
        question: str,
        language: str = None,
        top_k: int = 3,
        llm_model: str = None,
    ) -> Dict[str, Any]:
        """
        Pipeline RAG completo:
        1. Busca semântica no OpenSearch  
        2. Monta contexto com os resultados  
        3. Envia para Ollama gerar resposta  
        """
        if COMM_BUS_AVAILABLE:
            log_task_start("opensearch_agent", f"rag_{hash(question) % 10000}", f"RAG query: {question[:80]}")

        # 1. Busca semântica
        search_result = await self.semantic_search(question, language=language, size=top_k)
        context_chunks = [h["text"] for h in search_result.get("hits", []) if h.get("text")]

        if not context_chunks:
            # Fallback: busca full-text em docs e código
            docs_result = await self.search_docs(question, size=top_k)
            code_result = await self.search_code(question, language=language, size=top_k)
            for h in docs_result.get("hits", []):
                chunk = h.get("content", "")
                if chunk:
                    context_chunks.append(chunk[:1000])
            for h in code_result.get("hits", []):
                chunk = h.get("content", "") or h.get("description", "")
                if chunk:
                    context_chunks.append(chunk[:1000])

        context = "\n\n---\n\n".join(context_chunks) if context_chunks else "Nenhum contexto relevante encontrado."

        # 2. Montar prompt RAG
        model = llm_model or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        system_prompt = (
            "Você é um assistente técnico do projeto Eddie Auto-Dev. "
            "Responda com base no contexto fornecido. "
            "Se a informação não estiver no contexto, diga que não tem certeza. "
            "Responda em português do Brasil."
        )
        user_prompt = f"""CONTEXTO:
{context}

PERGUNTA:
{question}

Responda de forma concisa e precisa baseado no contexto acima."""

        # 3. Chamar Ollama
        try:
            resp = await self._ollama.post(
                "/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            answer = resp.json().get("message", {}).get("content", "")
        except Exception as e:
            answer = f"Erro ao consultar LLM: {e}"
            self._metrics["errors_total"] += 1

        if COMM_BUS_AVAILABLE:
            log_task_end("opensearch_agent", "rag_query", "RAG query completed")

        return {
            "question": question,
            "answer": answer,
            "sources": [
                {"text": c[:200], "index": i} for i, c in enumerate(context_chunks)
            ],
            "model": model,
            "search_hits": search_result.get("total", 0),
        }

    # ──────────── Bulk Ingestão ────────────

    async def ingest_codebase(
        self,
        directory: str,
        extensions: List[str] = None,
        agent: str = "opensearch_agent",
        project: str = "",
    ) -> Dict[str, Any]:
        """
        Indexa todos os arquivos de código de um diretório.
        Ideal para rodar no homelab via SSH.
        """
        import pathlib

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cs": "csharp",
            ".php": "php",
        }
        if extensions is None:
            extensions = list(ext_map.keys())

        path = pathlib.Path(directory)
        if not path.exists():
            return {"error": f"Directory not found: {directory}"}

        indexed = 0
        errors = 0
        for ext in extensions:
            for filepath in path.rglob(f"*{ext}"):
                # Pular node_modules, .venv, __pycache__, .git
                parts = filepath.parts
                if any(
                    p in parts
                    for p in ("node_modules", ".venv", "__pycache__", ".git", "venv")
                ):
                    continue

                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    if len(content) > 100_000:
                        content = content[:100_000]  # Limitar tamanho

                    lang = ext_map.get(ext, "unknown")
                    result = await self.index_code(
                        code=content,
                        language=lang,
                        filename=filepath.name,
                        filepath=str(filepath.relative_to(path)),
                        agent=agent,
                        project=project,
                    )
                    if "error" not in result:
                        indexed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        return {"indexed": indexed, "errors": errors, "directory": directory}

    async def ingest_docs(
        self,
        directory: str,
        category: str = "documentation",
    ) -> Dict[str, Any]:
        """Indexa arquivos .md de documentação."""
        import pathlib

        path = pathlib.Path(directory)
        if not path.exists():
            return {"error": f"Directory not found: {directory}"}

        indexed = 0
        errors = 0
        for md_file in path.rglob("*.md"):
            parts = md_file.parts
            if any(p in parts for p in ("node_modules", ".venv", ".git")):
                continue

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                title = md_file.stem.replace("_", " ").replace("-", " ").title()
                result = await self.index_doc_content(
                    title=title,
                    content=content[:50_000],
                    category=category,
                    tags=[category, md_file.suffix],
                    source_file=str(md_file.relative_to(path)),
                )
                if "error" not in result:
                    indexed += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        return {"indexed": indexed, "errors": errors, "directory": directory}

    async def ingest_for_rag(
        self,
        texts: List[str],
        language: str = "",
        source: str = "",
        chunk_size: int = 1500,
        chunk_overlap: int = 300,
    ) -> Dict[str, Any]:
        """Indexa textos com embeddings para RAG, dividindo em chunks."""
        indexed = 0
        errors = 0

        for i, text in enumerate(texts):
            # Dividir em chunks
            chunks = self._chunk_text(text, chunk_size, chunk_overlap)
            for j, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(f"{source}:{i}:{j}".encode()).hexdigest()[:16]
                result = await self.index_for_rag(
                    text=chunk,
                    language=language,
                    source=source,
                    metadata={"original_index": i, "chunk_index": j},
                    chunk_id=chunk_id,
                )
                if "error" not in result:
                    indexed += 1
                else:
                    errors += 1

        return {"indexed": indexed, "errors": errors, "chunks_total": indexed + errors}

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
        """Divide texto em chunks com overlap."""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    # ──────────── Métricas ────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do agente."""
        return {**self._metrics, "timestamp": datetime.now(timezone.utc).isoformat()}


# ──────────── Singleton ────────────

_opensearch_agent: Optional[OpenSearchAgent] = None


def get_opensearch_agent() -> OpenSearchAgent:
    """Retorna instância singleton do OpenSearch Agent."""
    global _opensearch_agent
    if _opensearch_agent is None:
        _opensearch_agent = OpenSearchAgent()
    return _opensearch_agent
