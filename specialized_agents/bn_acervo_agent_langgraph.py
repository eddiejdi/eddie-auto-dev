"""
BnAcervoAgent LangGraph — wrapper de governança LangGraph sobre o BnAcervoAgent.

Adiciona:
  - Action Journal: toda investigação gera intent_id rastreável
  - Shared Memory: resultados indexados no ChromaDB
  - Checkpoint: estado preservado durante investigações longas (browser + LLM)
  - Feature flag: BN_ACERVO_AGENT_VERSION=v2 ativa este wrapper (v1 é o padrão)

Risk levels::
    jobs/status (GET)       → low  (leitura)
    story                   → medium (web search + browser + LLM)
    dossier                 → medium (web search + browser + LLM, escopo maior)
    jobs (POST, criar)      → medium (lança browser + LLM assíncronos)
    jobs/cancel-active      → medium (interrompe jobs em andamento)

Env vars::
    BN_ACERVO_AGENT_VERSION — v1 (default) | v2
    DATABASE_URL            — obrigatório para checkpointer
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

logger = logging.getLogger(__name__)


def _run_async(coro) -> Any:
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result(timeout=600)
    except RuntimeError:
        return asyncio.run(coro)


# ── Story Agent (risk=medium) ─────────────────────────────────────────────────

class BnAcervoStoryAgent(HomelabAgent):
    AGENT_ID    = "bn_acervo_agent"
    ACTION_TYPE = "bn_acervo_story"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        query = state.get("extra", {}).get("query", "?")[:100]
        return f"BN Acervo story: {query}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.bn_acervo_agent import BnAcervoAgent, AcervoStoryRequest
        extra  = state.get("extra", {})
        req    = AcervoStoryRequest(**extra)
        agent  = BnAcervoAgent()
        result = _run_async(agent.run(req))
        query  = req.query[:80]
        mode   = result.get("output_mode", req.output_mode or "story")
        sections = len(result.get("sections", []))
        outcome = f"BN Acervo story '{query}': mode={mode}, {sections} seção(ões)"
        return {
            "outcome":     outcome,
            "_result":     result,
            "memory_fact": f"bn_acervo_agent: story '{query}' mode={mode} sections={sections}",
        }


# ── Dossier Agent (risk=medium) ───────────────────────────────────────────────

class BnAcervoDossierAgent(HomelabAgent):
    AGENT_ID    = "bn_acervo_agent"
    ACTION_TYPE = "bn_acervo_dossier"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        query = state.get("extra", {}).get("query", "?")[:100]
        return f"BN Acervo dossier: {query}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.bn_acervo_agent import BnAcervoAgent, AcervoStoryRequest
        extra  = state.get("extra", {})
        req    = AcervoStoryRequest(**extra)
        req    = req.model_copy(update={"output_mode": "dossier"})
        agent  = BnAcervoAgent()
        result = _run_async(agent.run(req))
        query  = req.query[:80]
        entities = len(result.get("entities", []))
        outcome = f"BN Acervo dossier '{query}': {entities} entidade(s)"
        return {
            "outcome":     outcome,
            "_result":     result,
            "memory_fact": f"bn_acervo_agent: dossier '{query}' entities={entities}",
        }


# ── Job Create Agent (risk=medium) ────────────────────────────────────────────

class BnAcervoJobAgent(HomelabAgent):
    AGENT_ID    = "bn_acervo_agent"
    ACTION_TYPE = "bn_acervo_job_create"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        query = state.get("extra", {}).get("query", "?")[:100]
        return f"BN Acervo criar job: {query}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.bn_acervo_agent import (
            BnAcervoAgent, AcervoStoryRequest,
            _reconcile_active_jobs, _run_bn_acervo_job, _JOB_TASKS,
        )
        from fastapi import HTTPException
        extra  = state.get("extra", {})
        req    = AcervoStoryRequest(**extra)
        agent  = BnAcervoAgent()
        active_jobs = _reconcile_active_jobs(agent.job_store)
        if active_jobs:
            active = active_jobs[0]
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "active_job_exists",
                    "message": "Já existe um processamento em andamento para o BN Acervo.",
                    "active_job_id": str(active.get("job_id") or ""),
                    "phase": str(active.get("phase") or ""),
                    "status": str(active.get("status") or ""),
                },
            )
        record = agent.job_store.create(req)
        job_id = str(record["job_id"])
        req_dossier = req.model_copy(
            update={"output_mode": "dossier"} if req.output_mode == "dossier" else {}
        )
        task = asyncio.ensure_future(_run_bn_acervo_job(job_id, req_dossier))
        _JOB_TASKS[job_id] = task
        outcome = f"BN Acervo job criado: job_id={job_id}, query='{req.query[:60]}'"
        return {
            "outcome":     outcome,
            "_result":     record,
            "memory_fact": f"bn_acervo_agent: job_create job_id={job_id} query='{req.query[:60]}'",
        }


# ── Cancel Agent (risk=medium) ────────────────────────────────────────────────

class BnAcervoCancelAgent(HomelabAgent):
    AGENT_ID    = "bn_acervo_agent"
    ACTION_TYPE = "bn_acervo_cancel"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        return "BN Acervo cancelar jobs ativos"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.bn_acervo_agent import (
            BnAcervoAgent, _reconcile_active_jobs, _cancel_job,
        )
        agent = BnAcervoAgent()
        active_jobs = _reconcile_active_jobs(agent.job_store)
        cancelled: list[str] = []
        for record in active_jobs:
            job_id = str(record.get("job_id") or "").strip()
            if not job_id:
                continue
            _run_async(_cancel_job(agent.job_store, job_id, reason="cancelled_by_operator"))
            cancelled.append(job_id)
        outcome = f"BN Acervo jobs cancelados: {cancelled}"
        return {
            "outcome":     outcome,
            "_result":     {"status": "ok", "cancelled_job_ids": cancelled, "count": len(cancelled)},
            "memory_fact": f"bn_acervo_agent: cancelled {len(cancelled)} job(s): {cancelled}",
        }


# ── Facade ────────────────────────────────────────────────────────────────────

class BnAcervoAgentLangraph:
    """Drop-in façade para os endpoints do bn_acervo_agent com governança LangGraph."""

    def __init__(self) -> None:
        self._story_agent  = BnAcervoStoryAgent()
        self._dossier_agent = BnAcervoDossierAgent()
        self._job_agent    = BnAcervoJobAgent()
        self._cancel_agent = BnAcervoCancelAgent()

    def close(self) -> None:
        for a in (self._story_agent, self._dossier_agent, self._job_agent, self._cancel_agent):
            a.close()

    def _unwrap(self, state: dict) -> dict:
        if state.get("approval") == "pending":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=202,
                detail=f"Aguardando aprovação Telegram. thread_id={state.get('thread_id')}",
            )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "operation failed"))
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}

    async def story(self, payload) -> dict[str, Any]:
        state = await asyncio.to_thread(
            self._story_agent.run,
            target=payload.query[:60],
            extra=payload.model_dump(),
        )
        return self._unwrap(state)

    async def dossier(self, payload) -> dict[str, Any]:
        state = await asyncio.to_thread(
            self._dossier_agent.run,
            target=payload.query[:60],
            extra=payload.model_copy(update={"output_mode": "dossier"}).model_dump(),
        )
        return self._unwrap(state)

    async def create_job(self, payload) -> dict[str, Any]:
        state = await asyncio.to_thread(
            self._job_agent.run,
            target=payload.query[:60],
            extra=payload.model_dump(),
        )
        return self._unwrap(state)

    async def cancel_active_jobs(self) -> dict[str, Any]:
        state = await asyncio.to_thread(
            self._cancel_agent.run,
            target="cancel_active",
            extra={},
        )
        return self._unwrap(state)


# ── Singleton ─────────────────────────────────────────────────────────────────

_agent: BnAcervoAgentLangraph | None = None


def get_bn_acervo_agent_langgraph() -> BnAcervoAgentLangraph:
    global _agent
    if _agent is None:
        _agent = BnAcervoAgentLangraph()
    return _agent
