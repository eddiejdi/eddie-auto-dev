"""
WikiAgent LangGraph — wrapper de governança LangGraph sobre o WikiAgent.

Adiciona ao WikiAgent existente:
  - Action Journal: toda operação gera um registro intent_id
  - Shared Memory: resultados indexados no ChromaDB após publicação
  - Checkpointing: estado preservado se o processo reiniciar durante geração Copilot
  - Feature flag: WIKI_AGENT_VERSION=v2 ativa este wrapper (v1 é o padrão)

Interface idêntica à v1:
  publish(WikiPublishRequest) → WikiResponse
  evolve(WikiEvolveRequest)   → WikiResponse
  refactor_wiki(req)          → WikiRefactorResponse
  execute_skill(skill, req)   → Any

O wrapper não reimplementa a lógica de negócio — delega para WikiAgent (v1) internamente.
O LangGraph envolve a chamada com governança (declare → execute → store_memory → complete).

Env vars::
    WIKI_AGENT_VERSION   — v1 (default) | v2
    DATABASE_URL         — obrigatório para checkpointer
    CHROMA_DB_PATH       — ChromaDB path
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent
from specialized_agents.wiki_agent import (
    WikiAgent,
    WikiPublishRequest,
    WikiEvolveRequest,
    WikiRefactorRequest,
    WikiRefactorResponse,
    WikiResponse,
)

logger = logging.getLogger(__name__)


def _get_v1() -> WikiAgent:
    """Retorna instância singleton do WikiAgent v1."""
    from specialized_agents.wiki_agent import get_wiki_agent
    return get_wiki_agent()


def _run_async(coro) -> Any:
    """Executa uma corrotina a partir de contexto síncrono (LangGraph node)."""
    try:
        loop = asyncio.get_running_loop()
        # Já há um loop rodando (FastAPI) — usar run_in_executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(asyncio.run, coro)
            return future.result(timeout=300)
    except RuntimeError:
        # Sem loop ativo — rodar diretamente
        return asyncio.run(coro)


# ── Agentes por operação ────────────────────────────────────────────────────


class WikiPublishAgent(HomelabAgent):
    AGENT_ID    = "wiki_agent"
    ACTION_TYPE = "wiki_publish"
    RISK_LEVEL  = "low"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        path = req_data.get("wiki_path", "?")
        topic = req_data.get("topic", "?")
        return f"Publicar página wiki: {path} — {topic}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        req = WikiPublishRequest(**req_data)
        result: WikiResponse = _run_async(_get_v1().publish(req))
        if not result.ok:
            raise RuntimeError(f"Wiki publish falhou: {result.message}")
        return {
            "outcome":     f"Página {result.wiki_path} publicada (id={result.page_id}). {result.message}",
            "memory_fact": (
                f"wiki_agent: publicou '{result.wiki_path}' "
                f"model={result.model_used or 'skip'} "
                f"tags={req.tags}"
            ),
            "_wiki_result": result.model_dump(),
        }


class WikiEvolveAgent(HomelabAgent):
    AGENT_ID    = "wiki_agent"
    ACTION_TYPE = "wiki_evolve"
    RISK_LEVEL  = "low"

    def _describe_work(self, state: AgentState) -> str:
        path = state.get("extra", {}).get("wiki_path", "?")
        return f"Evoluir página wiki: {path}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        req = WikiEvolveRequest(**req_data)
        result: WikiResponse = _run_async(_get_v1().evolve(req))
        if not result.ok:
            raise RuntimeError(f"Wiki evolve falhou: {result.message}")
        return {
            "outcome":     f"Página {result.wiki_path} evoluída (id={result.page_id}). {result.message}",
            "memory_fact": (
                f"wiki_agent: evoluiu '{result.wiki_path}' "
                f"model={result.model_used or 'skip'}"
            ),
            "_wiki_result": result.model_dump(),
        }


# ── WikiAgentV2 — fachada pública ──────────────────────────────────────────


class WikiAgentV2:
    """Drop-in replacement do WikiAgent com camada de governança LangGraph."""

    def __init__(self):
        self._publish_agent = WikiPublishAgent()
        self._evolve_agent  = WikiEvolveAgent()

    def _close(self):
        self._publish_agent.close()
        self._evolve_agent.close()

    # ── Parity com WikiAgent v1 ──────────────────────────────────────────────

    async def publish(self, req: WikiPublishRequest) -> WikiResponse:
        state = await asyncio.to_thread(
            self._publish_agent.run,
            target   = req.wiki_path,
            extra    = req.model_dump(),
        )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "wiki_publish failed"))
        result_data = state.get("_wiki_result") or {}
        if result_data:
            return WikiResponse(**result_data)
        # Fallback: construir resposta a partir do outcome
        return WikiResponse(
            ok=True,
            wiki_path=req.wiki_path,
            message=state.get("outcome", "ok"),
        )

    async def evolve(self, req: WikiEvolveRequest) -> WikiResponse:
        state = await asyncio.to_thread(
            self._evolve_agent.run,
            target = req.wiki_path,
            extra  = req.model_dump(),
        )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "wiki_evolve failed"))
        result_data = state.get("_wiki_result") or {}
        if result_data:
            return WikiResponse(**result_data)
        return WikiResponse(
            ok=True,
            wiki_path=req.wiki_path,
            message=state.get("outcome", "ok"),
        )

    async def refactor_wiki(self, req: WikiRefactorRequest) -> WikiRefactorResponse:
        # refactor não tem fluxo LangGraph — delega direto para v1
        return await _get_v1().refactor_wiki(req)

    async def execute_skill(self, skill_name: str, payload: Any) -> Any:
        skills = {
            "publish":       self.publish,
            "evolve":        self.evolve,
            "refactor_wiki": self.refactor_wiki,
        }
        skill = skills.get(skill_name)
        if skill is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Skill não encontrada: {skill_name}")
        return await skill(payload)


# ── Singleton ────────────────────────────────────────────────────────────────

_agent_v2: WikiAgentV2 | None = None


def get_wiki_agent_langgraph() -> WikiAgentV2:
    global _agent_v2
    if _agent_v2 is None:
        _agent_v2 = WikiAgentV2()
    return _agent_v2
