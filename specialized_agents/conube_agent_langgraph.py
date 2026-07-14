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


class ConubeScheduledDailySummaryAgent(ConubeDailySummaryAgent):
    """Execução agendada (cron) — auto-aprovada (risk=low)."""

    ACTION_TYPE = "conube_daily_summary_scheduled"
    RISK_LEVEL  = "low"


# ── Remediation Agent (risk=high) ─────────────────────────────────────────────

class ConubeRemediationAgent(HomelabAgent):
    AGENT_ID    = "conube_agent"
    ACTION_TYPE = "conube_run_remediation"
    RISK_LEVEL  = "high"

    def _describe_work(self, state: AgentState) -> str:
        extra = state.get("extra", {})
        return (
            "Conube remediation: "
            f"close_periods_limit={extra.get('close_periods_limit', 12)}, "
            f"run_client_tasks={extra.get('run_client_tasks', True)}, "
            f"selenium_balances={extra.get('run_selenium_balances', True)}, "
            f"selenium_tasks={extra.get('run_selenium_tasks', True)}"
        )

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.conube_agent import _build_agent
        from specialized_agents.conube_remediation import (
            close_open_financial_periods,
            fetch_operational_summary,
            needs_remediation,
            remediate_client_pending_tasks,
            run_remediation,
        )

        extra = state.get("extra", {})
        headless = extra.get("headless")
        close_periods_limit = int(extra.get("close_periods_limit", 12))
        run_client_tasks = bool(extra.get("run_client_tasks", True))
        mode = str(extra.get("mode") or "full")
        agent = _build_agent(headless)
        try:
            try:
                execution_body = self._run_remediation_modes(
                    agent=agent,
                    extra=extra,
                    mode=mode,
                    close_periods_limit=close_periods_limit,
                    run_client_tasks=run_client_tasks,
                )
            except Exception as exc:
                execution_body = {
                    "status": "error",
                    "actions": [],
                    "error": str(exc),
                    "remediation_needed": True,
                }
            result = execution_body
        finally:
            agent.close()

        from specialized_agents.conube_remediation import notify_remediation_result

        if "telegram_notification_sent" not in result:
            result["telegram_notification_sent"] = notify_remediation_result(result, force=result.get("status") == "error")

        before_open = int((result.get("before") or {}).get("open_periods_count") or 0)
        after_open = int((result.get("after") or {}).get("open_periods_count") or before_open)
        actions_count = len(result.get("actions") or [])
        if result.get("status") == "error":
            outcome = f"Conube remediation failed: {result.get('error', 'unknown')}"
        else:
            outcome = (
                f"Conube remediation: status={result.get('status')}, "
                f"actions={actions_count}, open_periods {before_open}->{after_open}"
            )
        return {
            "outcome": outcome,
            "_result": result,
            "memory_fact": (
                f"conube_agent: remediation status={result.get('status')} "
                f"open_periods={after_open}"
            ),
        }

    def _run_remediation_modes(
        self,
        *,
        agent: Any,
        extra: dict[str, Any],
        mode: str,
        close_periods_limit: int,
        run_client_tasks: bool,
    ) -> dict[str, Any]:
        from specialized_agents.conube_remediation import (
            close_open_financial_periods,
            fetch_operational_summary,
            needs_remediation,
            remediate_client_pending_tasks,
            run_remediation,
        )

        if mode == "client_tasks":
            tasks_result = remediate_client_pending_tasks(agent)
            return {
                "status": tasks_result.get("status"),
                "actions": [
                    {
                        "action": "remediate-client-pending-tasks",
                        "status": tasks_result.get("status"),
                        "processed": tasks_result.get("processed", 0),
                        "result": tasks_result,
                    }
                ],
            }

        if mode == "close_periods":
            close_result = close_open_financial_periods(agent, limit=close_periods_limit)
            return {
                "status": close_result.get("status"),
                "actions": [
                    {
                        "action": "close-open-financial-periods",
                        "status": close_result.get("status"),
                        "processed": close_result.get("processed", 0),
                        "blocked": close_result.get("blocked", 0),
                        "result": close_result,
                    }
                ],
            }

        if mode == "selenium_balances":
            from specialized_agents.conube_selenium import close_overdue_balances_without_movement

            balances_result = close_overdue_balances_without_movement(
                agent,
                limit=int(extra.get("selenium_balances_limit", 12)),
            )
            return {
                "status": balances_result.get("status"),
                "actions": [
                    {
                        "action": "close-overdue-balances-selenium",
                        "status": balances_result.get("status"),
                        "processed": balances_result.get("processed", 0),
                        "result": balances_result,
                    }
                ],
            }

        if mode == "selenium_tasks":
            from specialized_agents.conube_selenium import remediate_pending_tasks_selenium

            tasks_result = remediate_pending_tasks_selenium(
                agent,
                limit=int(extra.get("selenium_tasks_limit", 20)),
            )
            return {
                "status": tasks_result.get("status"),
                "actions": [
                    {
                        "action": "remediate-pending-tasks-selenium",
                        "status": tasks_result.get("status"),
                        "processed": tasks_result.get("processed", 0),
                        "result": tasks_result,
                    }
                ],
            }

        before = fetch_operational_summary(agent)
        if not needs_remediation(before):
            return {
                "status": "ok",
                "actions": [],
                "before": before,
                "after": before,
                "remediation_needed": False,
            }

        return run_remediation(
            agent,
            close_periods_limit=close_periods_limit,
            run_client_tasks=run_client_tasks,
            run_selenium_balances=bool(extra.get("run_selenium_balances", True)),
            run_selenium_tasks=bool(extra.get("run_selenium_tasks", True)),
            selenium_balances_limit=int(extra.get("selenium_balances_limit", 12)),
            selenium_tasks_limit=int(extra.get("selenium_tasks_limit", 20)),
        )


class ConubeScheduledRemediationAgent(ConubeRemediationAgent):
    """Execução agendada de remediação — requer aprovação (risk=high)."""

    ACTION_TYPE = "conube_run_remediation_scheduled"


# ── Billing Payment Agent (risk=high, dinheiro real) ─────────────────────────

class ConubeBillingPaymentAgent(HomelabAgent):
    """Paga boletos pendentes da Conube (faturas Vindi) via Mercado Pago.

    Sempre exige aprovação Telegram: o intent carrega valor, vencimento e
    quantidade de faturas para o aprovador decidir com contexto.
    """

    AGENT_ID    = "conube_agent"
    ACTION_TYPE = "conube_pay_billing_boleto"
    RISK_LEVEL  = "high"

    def _describe_work(self, state: AgentState) -> str:
        extra = state.get("extra", {})
        total = extra.get("total_amount_brl") or "?"
        count = extra.get("pending_count", "?")
        dry_run = extra.get("dry_run", False)
        return (
            f"Pagar boleto Conube via Mercado Pago: {count} fatura(s), "
            f"total {total} (dry_run={dry_run})"
        )

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.conube_agent import _build_agent
        from specialized_agents.conube_billing import pay_pending_charges

        extra = state.get("extra", {})
        agent = _build_agent(extra.get("headless"))
        try:
            result = pay_pending_charges(
                agent,
                dry_run=bool(extra.get("dry_run", False)),
                limit=int(extra.get("limit", 3)),
            )
        finally:
            agent.close()

        paid = int(result.get("processed") or 0)
        pending = int(result.get("pending_count") or 0)
        outcome = (
            f"Conube billing: status={result.get('status')}, "
            f"pagas={paid}/{pending} (dry_run={result.get('dry_run')})"
        )
        return {
            "outcome": outcome,
            "_result": result,
            "memory_fact": f"conube_agent: billing boletos pagos={paid} pendentes={pending}",
        }


class ConubeScheduledBillingPaymentAgent(ConubeBillingPaymentAgent):
    """Disparo agendado (cron/remediação) — mesma aprovação obrigatória."""

    ACTION_TYPE = "conube_pay_billing_boleto_scheduled"


# ── Facade ────────────────────────────────────────────────────────────────────

class ConubeAgentLangraph:
    """Fachada com a mesma interface dos endpoints FastAPI do conube_agent v1."""

    def __init__(self) -> None:
        self._login_agent        = ConubeTestLoginAgent()
        self._summary_agent      = ConubeDailySummaryAgent()
        self._remediation_agent  = ConubeRemediationAgent()
        self._billing_agent      = ConubeBillingPaymentAgent()

    def close(self) -> None:
        self._login_agent.close()
        self._summary_agent.close()
        self._remediation_agent.close()
        self._billing_agent.close()

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

    def run_remediation(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        close_periods_limit = getattr(payload, "close_periods_limit", 12) if payload else 12
        run_client_tasks = getattr(payload, "run_client_tasks", True) if payload else True
        extra = {
            "headless": headless,
            "close_periods_limit": close_periods_limit,
            "run_client_tasks": run_client_tasks,
            "run_selenium_balances": getattr(payload, "run_selenium_balances", True) if payload else True,
            "run_selenium_tasks": getattr(payload, "run_selenium_tasks", True) if payload else True,
            "selenium_balances_limit": getattr(payload, "selenium_balances_limit", 12) if payload else 12,
            "selenium_tasks_limit": getattr(payload, "selenium_tasks_limit", 20) if payload else 20,
        }
        state = self._remediation_agent.run(target="conube_remediation", extra=extra)
        return self._unwrap(state)

    def close_overdue_balances(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        limit = getattr(payload, "limit", 12) if payload else 12
        extra = {"headless": headless, "mode": "selenium_balances", "selenium_balances_limit": limit}
        state = self._remediation_agent.run(target="conube_close_balances_selenium", extra=extra)
        return self._unwrap(state)

    def remediate_pending_selenium(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        limit = getattr(payload, "limit", 20) if payload else 20
        extra = {"headless": headless, "mode": "selenium_tasks", "selenium_tasks_limit": limit}
        state = self._remediation_agent.run(target="conube_remediate_tasks_selenium", extra=extra)
        return self._unwrap(state)

    def remediate_client_pending(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        extra = {"headless": headless, "mode": "client_tasks"}
        state = self._remediation_agent.run(target="conube_remediate_client", extra=extra)
        return self._unwrap(state)

    def pay_billing_boleto(self, payload: Any = None) -> dict[str, Any]:
        extra = {
            "headless": getattr(payload, "headless", None) if payload else None,
            "dry_run": getattr(payload, "dry_run", False) if payload else False,
            "limit": getattr(payload, "limit", 3) if payload else 3,
            "pending_count": getattr(payload, "pending_count", None) if payload else None,
            "total_amount_brl": getattr(payload, "total_amount_brl", None) if payload else None,
        }
        state = self._billing_agent.run(target="conube_billing_boleto", extra=extra)
        return self._unwrap(state)

    def close_open_financial_periods(self, payload: Any = None) -> dict[str, Any]:
        headless = getattr(payload, "headless", None) if payload else None
        limit = getattr(payload, "limit", 12) if payload else 12
        extra = {"headless": headless, "close_periods_limit": limit, "mode": "close_periods"}
        state = self._remediation_agent.run(target="conube_close_periods", extra=extra)
        return self._unwrap(state)


# ── Singleton ─────────────────────────────────────────────────────────────────

_agent: ConubeAgentLangraph | None = None


def get_conube_agent_langgraph() -> ConubeAgentLangraph:
    global _agent
    if _agent is None:
        _agent = ConubeAgentLangraph()
    return _agent


def run_scheduled_daily_summary(
    *,
    headless: bool | None = True,
    refresh: bool = True,
    use_ollama: bool = False,
) -> dict[str, Any]:
    """Runner usado pelo cron — governança v2 com risco low (auto-aprovado)."""
    agent = ConubeScheduledDailySummaryAgent()
    try:
        state = agent.run(
            target="conube_daily_summary_scheduled",
            description="Relatório diário Conube (cron)",
            extra={"headless": headless, "refresh": refresh, "use_ollama": use_ollama},
        )
        if state.get("approval") == "pending":
            raise RuntimeError(
                f"Relatório agendado parou aguardando aprovação (thread_id={state.get('thread_id')})"
            )
        if state.get("status") == "failed":
            raise RuntimeError(state.get("error") or "falha no relatório agendado")
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}
    finally:
        agent.close()


def run_scheduled_remediation(
    *,
    headless: bool | None = True,
    close_periods_limit: int = 12,
    run_client_tasks: bool = True,
) -> dict[str, Any]:
    """Runner usado pelo cron — governança v2 com risco high (aprovação Telegram)."""
    agent = ConubeScheduledRemediationAgent()
    try:
        state = agent.run(
            target="conube_run_remediation_scheduled",
            description="Remediação operacional Conube (cron)",
            extra={
                "headless": headless,
                "close_periods_limit": close_periods_limit,
                "run_client_tasks": run_client_tasks,
            },
        )
        if state.get("approval") == "pending":
            return {
                "status": "pending_approval",
                "thread_id": state.get("thread_id"),
                "intent_id": state.get("intent_id"),
            }
        if state.get("status") == "failed":
            raise RuntimeError(state.get("error") or "falha na remediação agendada")
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}
    finally:
        agent.close()
