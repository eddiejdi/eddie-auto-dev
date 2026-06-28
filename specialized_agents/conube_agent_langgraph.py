"""
ConubeAgent LangGraph — wrapper de governança LangGraph sobre o ConubeAgent.

Adiciona:
  - Action Journal: toda operação Selenium gera intent_id rastreável
  - Shared Memory: resultados indexados no ChromaDB após execução
  - Checkpoint: estado preservado se o processo reiniciar
  - Feature flag: CONUBE_AGENT_VERSION=v2 ativa este wrapper (v1 é o padrão)

Risk levels::
    health                → low  (leitura, sem browser)
    session/test-login    → medium (Selenium + credenciais externas)
    reports/daily-summary → medium (Selenium + credenciais + report)

Env vars::
    CONUBE_AGENT_VERSION — v1 (default) | v2
    DATABASE_URL         — obrigatório para checkpointer
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent

logger = logging.getLogger(__name__)


# ── Test Login Agent (risk=medium) ───────────────────────────────────────────

class ConubeTestLoginAgent(HomelabAgent):
    AGENT_ID    = "conube_agent"
    ACTION_TYPE = "conube_test_login"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        headless = state.get("extra", {}).get("headless", True)
        return f"Conube login test (headless={headless})"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.conube_agent import _build_agent, ConubeActionRequest
        extra    = state.get("extra", {})
        headless = extra.get("headless")
        req      = ConubeActionRequest(headless=headless) if headless is not None else None
        agent    = _build_agent(req.headless if req else None)
        try:
            result = agent.login()
        finally:
            agent.close()
        authenticated = result.get("authenticated", False)
        outcome = f"Conube login: authenticated={authenticated}, url={result.get('current_url', '?')[:80]}"
        return {
            "outcome":     outcome,
            "_result":     result,
            "memory_fact": f"conube_agent: login authenticated={authenticated}",
        }


# ── Daily Summary Agent (risk=medium) ────────────────────────────────────────

class ConubeDailySummaryAgent(HomelabAgent):
    AGENT_ID    = "conube_agent"
    ACTION_TYPE = "conube_daily_summary"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        extra   = state.get("extra", {})
        refresh = extra.get("refresh", False)
        return f"Conube daily summary (refresh={refresh})"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.conube_agent import _build_agent, _build_degraded_report, CONUBE_LOGIN_URL
        extra      = state.get("extra", {})
        headless   = extra.get("headless")
        refresh    = extra.get("refresh", False)
        use_ollama = extra.get("use_ollama", True)
        agent      = _build_agent(headless)
        try:
            try:
                login_result = agent.login()
            except Exception as exc:
                login_result = {
                    "authenticated": False,
                    "token_present": False,
                    "current_url": CONUBE_LOGIN_URL,
                    "title": "Conube",
                    "menu_items": [],
                    "failure_reason": str(exc),
                }
            result = _build_degraded_report(login_result, refresh=refresh, use_ollama=use_ollama)
        finally:
            agent.close()
        authenticated = login_result.get("authenticated", False)
        sections_count = len(result.get("sections", []))
        outcome = f"Conube daily summary: authenticated={authenticated}, {sections_count} seção(ões)"
        return {
            "outcome":     outcome,
            "_result":     result,
            "memory_fact": f"conube_agent: daily_summary authenticated={authenticated} sections={sections_count}",
        }


# ── Facade ────────────────────────────────────────────────────────────────────

class ConubeAgentLangraph:
    """Fachada com a mesma interface dos endpoints FastAPI do conube_agent v1."""

    def __init__(self) -> None:
        self._login_agent   = ConubeTestLoginAgent()
        self._summary_agent = ConubeDailySummaryAgent()

    def close(self) -> None:
        self._login_agent.close()
        self._summary_agent.close()

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

    def test_login(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        extra    = {"headless": headless} if headless is not None else {}
        state    = self._login_agent.run(target="conube_login", extra=extra)
        return self._unwrap(state)

    def daily_summary(
        self,
        headless: bool | None = None,
        refresh: bool = False,
        use_ollama: bool = True,
    ) -> dict[str, Any]:
        extra = {"headless": headless, "refresh": refresh, "use_ollama": use_ollama}
        state = self._summary_agent.run(target="conube_daily_summary", extra=extra)
        return self._unwrap(state)


# ── Singleton ─────────────────────────────────────────────────────────────────

_agent: ConubeAgentLangraph | None = None


def get_conube_agent_langgraph() -> ConubeAgentLangraph:
    global _agent
    if _agent is None:
        _agent = ConubeAgentLangraph()
    return _agent
