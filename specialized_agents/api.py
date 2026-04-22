"""Specialized Agents API - FastAPI entry point.

Centraliza todos os routers de agentes especializados:
- Conube (automação/banking)
- RAG (conhecimento)
- Agentes (status/health)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Criar app FastAPI
app = FastAPI(
    title="Specialized Agents API",
    version="2026.03.15",
    description="Multi-agent system orchestration"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ROUTERS EXISTENTES (importar de módulos)
# ============================================================================

try:
    from .conube_agent import router as conube_router
    app.include_router(conube_router, prefix="/conube", tags=["conube"])
    logger.info("✅ Conube router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Conube router não disponível: {e}")

try:
    from .agent_communication_bus import router as comm_router
    app.include_router(comm_router, prefix="/communication", tags=["communication"])
    logger.info("✅ Communication router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Communication router não disponível: {e}")

try:
    from .copilot_routes import router as copilot_router
    app.include_router(copilot_router, tags=["copilot"])
    logger.info("✅ Copilot router carregado (modelo com fallback OpenAI-compatible)")
except ImportError as e:
    logger.warning(f"⚠️  Copilot router não disponível: {e}")

# ============================================================================
# NOVOS ENDPOINTS: RAG, AGENTS, BANKING
# ============================================================================

# Health check geral
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check da API."""
    return {
        "status": "ok",
        "service": "specialized-agents-api",
        "version": "2026.03.15"
    }


@app.head("/health")
async def health_check_head() -> dict[str, Any]:
    """Head health check da API."""
    return await health_check()


# ============================================================================
# RAG (Retrieval-Augmented Generation)
# ============================================================================

rag_router = APIRouter()


@rag_router.get("/index")
async def rag_index() -> dict[str, Any]:
    """Obter índice de documentos RAG."""
    try:
        # TODO: Conectar com RAG backend real
        return {
            "status": "operational",
            "documents": {
                "total": 0,
                "indexed": 0,
                "categories": []
            },
            "last_update": None
        }
    except Exception as e:
        logger.error(f"RAG index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.post("/query")
async def rag_query(query: str, top_k: int = 5) -> dict[str, Any]:
    """Buscar documentos RAG."""
    try:
        # TODO: Implementar retrieval real
        return {
            "query": query,
            "results": [],
            "count": 0
        }
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(rag_router, prefix="/rag", tags=["rag"])

# ============================================================================
# AGENTS (Status centralizador)
# ============================================================================

agents_router = APIRouter()


@agents_router.get("/status")
async def agents_status() -> dict[str, Any]:
    """Status de todos os agentes especializados."""
    try:
        return {
            "agents": {
                "trading": {
                    "status": "unknown",
                    "last_activity": None,
                    "trades_24h": None
                },
                "rag": {
                    "status": "unknown",
                    "documents_indexed": 0
                },
                "communication": {
                    "status": "unknown",
                    "messages_pending": None
                }
            },
            "timestamp": None
        }
    except Exception as e:
        logger.error(f"Agents status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agents_router.get("/{agent_id}/health")
async def agent_health(agent_id: str) -> dict[str, Any]:
    """Health check de um agente específico."""
    try:
        return {
            "agent_id": agent_id,
            "status": "unknown",
            "uptime_seconds": None
        }
    except Exception as e:
        logger.error(f"Agent health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(agents_router, prefix="/agents", tags=["agents"])

# ============================================================================
# BANKING (Status bancário/financeiro)
# ============================================================================

banking_router = APIRouter()


@banking_router.get("/status")
async def banking_status() -> dict[str, Any]:
    """Status do sistema bancário/financeiro."""
    try:
        return {
            "balance": None,
            "accounts": [],
            "pending_transactions": 0
        }
    except Exception as e:
        logger.error(f"Banking status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(banking_router, prefix="/banking", tags=["banking"])

# ============================================================================
# Outros routers existentes (puxar de pastas)
# ============================================================================

try:
    from .home_automation import router as ha_router
    app.include_router(ha_router, prefix="/home-automation", tags=["home-automation"])
    logger.info("✅ Home Automation router carregado")
except (ImportError, AttributeError) as e:
    logger.debug(f"Home Automation router não disponível: {e}")

try:
    from .banking import router as banking_module_router
    app.include_router(banking_module_router, prefix="/banking-module", tags=["banking-module"])
    logger.info("✅ Banking module router carregado")
except (ImportError, AttributeError) as e:
    logger.debug(f"Banking module router não disponível: {e}")

logger.info("✅ Specialized Agents API initializado com sucesso")
