"""
OpenSearch Routes — Endpoints FastAPI para o OpenSearch Agent.
Integra busca, indexação, RAG e observabilidade via API REST.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/opensearch", tags=["opensearch"])


# ──────────── Models ────────────

class IndexCodeRequest(BaseModel):
    code: str
    language: str
    filename: str
    filepath: str = ""
    agent: str = ""
    project: str = ""
    description: str = ""


class IndexLogRequest(BaseModel):
    message: str
    level: str = "INFO"
    service: str = ""
    agent: str = ""
    task_id: str = ""
    conversation_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IndexDocRequest(BaseModel):
    title: str
    content: str
    category: str = "documentation"
    tags: List[str] = Field(default_factory=list)
    source_file: str = ""


class RAGIndexRequest(BaseModel):
    texts: List[str]
    language: str = ""
    source: str = ""
    chunk_size: int = 1500
    chunk_overlap: int = 300


class RAGQueryRequest(BaseModel):
    question: str
    language: Optional[str] = None
    top_k: int = 3
    llm_model: Optional[str] = None


class SemanticSearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    size: int = 5
    min_score: float = 0.5


class IngestRequest(BaseModel):
    directory: str
    extensions: Optional[List[str]] = None
    agent: str = "opensearch_agent"
    project: str = ""
    category: str = "documentation"


class BulkIndexRequest(BaseModel):
    index_name: str
    documents: List[Dict[str, Any]]
    id_field: Optional[str] = None


# ──────────── Helpers ────────────

def _get_agent():
    """Lazy import para evitar erro circular."""
    from specialized_agents.opensearch_agent import get_opensearch_agent
    return get_opensearch_agent()


# ──────────── Health & Info ────────────

@router.get("/health")
async def opensearch_health():
    """Verifica saúde do OpenSearch cluster."""
    agent = _get_agent()
    return await agent.health()


@router.get("/info")
async def opensearch_info():
    """Informações do cluster OpenSearch."""
    agent = _get_agent()
    return await agent.cluster_info()


@router.get("/indices")
async def opensearch_indices():
    """Lista índices do OpenSearch."""
    agent = _get_agent()
    return await agent.list_indices()


@router.get("/metrics")
async def opensearch_metrics():
    """Métricas do agente OpenSearch."""
    agent = _get_agent()
    return agent.get_metrics()


# ──────────── Setup ────────────

@router.post("/setup")
async def opensearch_setup():
    """Cria todos os índices padrão do Eddie."""
    agent = _get_agent()
    return await agent.setup_default_indices()


# ──────────── Indexação ────────────

@router.post("/index/code")
async def index_code(req: IndexCodeRequest):
    """Indexa um arquivo de código."""
    agent = _get_agent()
    return await agent.index_code(
        code=req.code,
        language=req.language,
        filename=req.filename,
        filepath=req.filepath,
        agent=req.agent,
        project=req.project,
        description=req.description,
    )


@router.post("/index/log")
async def index_log(req: IndexLogRequest):
    """Indexa uma entrada de log."""
    agent = _get_agent()
    return await agent.index_log(
        message=req.message,
        level=req.level,
        service=req.service,
        agent=req.agent,
        task_id=req.task_id,
        conversation_id=req.conversation_id,
        metadata=req.metadata,
    )


@router.post("/index/doc")
async def index_doc(req: IndexDocRequest):
    """Indexa documentação."""
    agent = _get_agent()
    return await agent.index_doc_content(
        title=req.title,
        content=req.content,
        category=req.category,
        tags=req.tags,
        source_file=req.source_file,
    )


@router.post("/index/rag")
async def index_rag(req: RAGIndexRequest):
    """Indexa textos com embeddings para RAG."""
    agent = _get_agent()
    return await agent.ingest_for_rag(
        texts=req.texts,
        language=req.language,
        source=req.source,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
    )


@router.post("/index/bulk")
async def bulk_index(req: BulkIndexRequest):
    """Indexa documentos em bulk."""
    agent = _get_agent()
    return await agent.bulk_index(
        index_name=req.index_name,
        documents=req.documents,
        id_field=req.id_field,
    )


# ──────────── Ingestão de diretórios ────────────

@router.post("/ingest/code")
async def ingest_code(req: IngestRequest):
    """Indexa todos os arquivos de código de um diretório."""
    agent = _get_agent()
    return await agent.ingest_codebase(
        directory=req.directory,
        extensions=req.extensions,
        agent=req.agent,
        project=req.project,
    )


@router.post("/ingest/docs")
async def ingest_docs(req: IngestRequest):
    """Indexa arquivos .md de um diretório."""
    agent = _get_agent()
    return await agent.ingest_docs(
        directory=req.directory,
        category=req.category,
    )


# ──────────── Busca ────────────

@router.get("/search/code")
async def search_code(
    q: str = Query(..., description="Texto de busca"),
    language: Optional[str] = Query(None, description="Filtrar por linguagem"),
    size: int = Query(10, ge=1, le=100),
):
    """Busca full-text em código indexado."""
    agent = _get_agent()
    return await agent.search_code(q, language=language, size=size)


@router.get("/search/logs")
async def search_logs(
    q: Optional[str] = Query(None, description="Texto de busca"),
    level: Optional[str] = Query(None, description="Nível do log"),
    service: Optional[str] = Query(None, description="Nome do serviço"),
    agent_name: Optional[str] = Query(None, alias="agent", description="Nome do agente"),
    since: Optional[str] = Query(None, description="Data mínima (ISO 8601)"),
    size: int = Query(50, ge=1, le=500),
):
    """Busca em logs."""
    agent_instance = _get_agent()
    return await agent_instance.search_logs(
        query_text=q,
        level=level,
        service=service,
        agent=agent_name,
        since=since,
        size=size,
    )


@router.get("/search/docs")
async def search_docs(
    q: str = Query(..., description="Texto de busca"),
    category: Optional[str] = Query(None, description="Categoria"),
    size: int = Query(10, ge=1, le=100),
):
    """Busca em documentação."""
    agent = _get_agent()
    return await agent.search_docs(q, category=category, size=size)


@router.post("/search/semantic")
async def semantic_search(req: SemanticSearchRequest):
    """Busca semântica vetorial (k-NN) para RAG."""
    agent = _get_agent()
    return await agent.semantic_search(
        query_text=req.query,
        language=req.language,
        size=req.size,
        min_score=req.min_score,
    )


# ──────────── RAG ────────────

@router.post("/rag/query")
async def rag_query(req: RAGQueryRequest):
    """
    Pipeline RAG completo:
    busca semântica → monta contexto → gera resposta via LLM.
    """
    agent = _get_agent()
    return await agent.rag_query(
        question=req.question,
        language=req.language,
        top_k=req.top_k,
        llm_model=req.llm_model,
    )


# ──────────── Delete ────────────

@router.delete("/index/{index_name}")
async def delete_index(index_name: str):
    """Remove um índice."""
    agent = _get_agent()
    # Proteção: não deletar índices do sistema
    if not index_name.startswith("eddie-"):
        raise HTTPException(status_code=400, detail="Apenas índices 'eddie-*' podem ser removidos.")
    return await agent.delete_index(index_name)
