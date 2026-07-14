"""Auto-resume de intenções aprovadas no Agent Governance Layer.

Após aprovação humana (Telegram), executa o trabalho pendente e fecha o
registro no Action Journal. Se o checkpoint LangGraph não estiver disponível
(ex.: MemorySaver em outro processo), reexecuta o trabalho diretamente.
"""
from __future__ import annotations

import json
import logging
import traceback
from typing import Any, Callable

from specialized_agents.langgraph_base import (
    AgentState,
    HomelabAgent,
    _intent_check,
    _intent_complete,
    _memory_store,
)

logger = logging.getLogger(__name__)

AgentFactory = Callable[[], HomelabAgent]


def _db_connect():
    import psycopg2

    from specialized_agents.langgraph_base import _resolve_db_url

    return psycopg2.connect(_resolve_db_url())


def _fetch_intent(intent_id: str) -> dict[str, Any] | None:
    conn = _db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_actions WHERE intent_id = %s", (intent_id,))
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
            data = dict(zip(columns, row))
            ctx = data.get("context_snapshot")
            if isinstance(ctx, str):
                try:
                    data["context_snapshot"] = json.loads(ctx)
                except json.JSONDecodeError:
                    data["context_snapshot"] = {}
            elif ctx is None:
                data["context_snapshot"] = {}
            return data
    finally:
        conn.close()


def _mark_in_progress(intent_id: str) -> bool:
    conn = _db_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_actions
                       SET status = 'in_progress',
                           executed_at = COALESCE(executed_at, NOW())
                     WHERE intent_id = %s
                       AND status = 'approved'
                    """,
                    (intent_id,),
                )
                return cur.rowcount == 1
    finally:
        conn.close()


def _agent_registry() -> dict[tuple[str, str], AgentFactory]:
    from specialized_agents.conube_agent_langgraph import (
        ConubeBillingPaymentAgent,
        ConubeDailySummaryAgent,
        ConubeRemediationAgent,
        ConubeTestLoginAgent,
    )

    registry: dict[tuple[str, str], AgentFactory] = {
        ("conube_agent", "conube_test_login"): ConubeTestLoginAgent,
        ("conube_agent", "conube_daily_summary"): ConubeDailySummaryAgent,
        ("conube_agent", "conube_run_remediation"): ConubeRemediationAgent,
        ("conube_agent", "conube_run_remediation_scheduled"): ConubeRemediationAgent,
        ("conube_agent", "conube_pay_billing_boleto"): ConubeBillingPaymentAgent,
        ("conube_agent", "conube_pay_billing_boleto_scheduled"): ConubeBillingPaymentAgent,
    }

    try:
        from specialized_agents.ltfs_log_rotation_agent import LtfsLogRotationAgent

        registry[("ltfs_log_rotation", "ltfs_rotate_logs")] = LtfsLogRotationAgent
    except Exception:
        pass

    return registry


def _resolve_agent(agent_id: str, action_type: str) -> HomelabAgent | None:
    factory = _agent_registry().get((agent_id, action_type))
    if not factory:
        logger.warning("Sem agente registrado para %s/%s", agent_id, action_type)
        return None
    return factory()


def _state_from_intent(intent: dict[str, Any]) -> AgentState:
    ctx = intent.get("context_snapshot") or {}
    return {
        "agent_id": intent.get("agent_id", ""),
        "action_type": intent.get("action_type", ""),
        "target": ctx.get("target") or intent.get("target") or "",
        "description": intent.get("description", ""),
        "risk_level": intent.get("risk_level", "medium"),
        "extra": ctx.get("extra") or {},
        "intent_id": intent.get("intent_id", ""),
        "approval": "approved",
        "thread_id": ctx.get("thread_id", ""),
        "status": "running",
    }


def _finalize_success(intent_id: str, state: AgentState, result: dict[str, Any]) -> AgentState:
    outcome = result.get("outcome", "ok")
    memory_fact = result.get("memory_fact", "")
    merged: AgentState = {
        **state,
        "outcome": outcome,
        "memory_fact": memory_fact,
        "status": "done",
    }
    if "_result" in result:
        merged["_result"] = result["_result"]
    if memory_fact:
        try:
            _memory_store(
                fact=memory_fact,
                source="agent",
                tags=[state.get("action_type", ""), state.get("risk_level", "")],
                agent_id=state.get("agent_id", "unknown"),
            )
        except Exception:
            logger.debug("store_memory falhou (best-effort)", exc_info=True)
    _intent_complete(intent_id=intent_id, outcome=outcome, error=None)
    return merged


def _execute_direct(agent: HomelabAgent, intent: dict[str, Any]) -> AgentState:
    state = _state_from_intent(intent)
    result = agent._execute_work(state)
    return _finalize_success(intent["intent_id"], state, result)


def _try_langgraph_resume(agent: HomelabAgent, intent: dict[str, Any]) -> AgentState | None:
    ctx = intent.get("context_snapshot") or {}
    thread_id = str(ctx.get("thread_id") or "").strip()
    if not thread_id:
        return None
    try:
        state = agent.resume(thread_id)
    except Exception as exc:
        logger.info(
            "Resume LangGraph indisponível para %s (%s); fallback direto.",
            intent.get("intent_id"),
            exc,
        )
        return None

    approval = state.get("approval")
    status = state.get("status")
    if approval == "rejected" or status == "rejected":
        _intent_complete(intent_id=intent["intent_id"], outcome="Rejeitado pelo operador", error=None)
        return state
    if approval == "pending" or not state.get("outcome"):
        return None
    if status == "failed":
        _intent_complete(
            intent_id=intent["intent_id"],
            outcome="",
            error=state.get("error") or "operation failed",
        )
        return state
    if state.get("intent_id"):
        _intent_complete(intent_id=state["intent_id"], outcome=state.get("outcome", ""), error=None)
    return state


def resume_approved_intent(intent_id: str) -> dict[str, Any]:
    """Executa uma intenção já aprovada. Idempotente para intents concluídas."""
    intent = _fetch_intent(intent_id)
    if not intent:
        return {"ok": False, "intent_id": intent_id, "error": "intent não encontrado"}

    status = intent.get("status")
    if status in ("done", "failed", "rejected", "expired"):
        return {
            "ok": True,
            "intent_id": intent_id,
            "status": status,
            "skipped": True,
            "outcome": intent.get("outcome"),
        }
    if status == "pending":
        return {"ok": False, "intent_id": intent_id, "error": "intent ainda pending"}
    if status not in ("approved", "in_progress"):
        return {"ok": False, "intent_id": intent_id, "error": f"status inesperado: {status}"}

    if status == "approved" and not _mark_in_progress(intent_id):
        latest = _fetch_intent(intent_id) or intent
        if latest.get("status") in ("done", "failed", "in_progress"):
            return {
                "ok": True,
                "intent_id": intent_id,
                "status": latest.get("status"),
                "skipped": True,
            }
        return {"ok": False, "intent_id": intent_id, "error": "não foi possível marcar in_progress"}

    agent = _resolve_agent(str(intent.get("agent_id", "")), str(intent.get("action_type", "")))
    if agent is None:
        _intent_complete(intent_id=intent_id, outcome="", error="agente não registrado para auto-resume")
        return {"ok": False, "intent_id": intent_id, "error": "agente não registrado"}

    try:
        resume_mode = "langgraph"
        state = _try_langgraph_resume(agent, intent)
        if state is None:
            resume_mode = "direct"
            state = _execute_direct(agent, intent)

        result_payload = state.get("_result") if isinstance(state.get("_result"), dict) else {}
        return {
            "ok": state.get("status") == "done",
            "intent_id": intent_id,
            "status": state.get("status"),
            "outcome": state.get("outcome"),
            "authenticated": result_payload.get("authenticated"),
            "resume_mode": resume_mode,
        }
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("Auto-resume falhou %s: %s\n%s", intent_id, err, traceback.format_exc()[-1200:])
        _intent_complete(intent_id=intent_id, outcome="", error=err)
        return {"ok": False, "intent_id": intent_id, "error": err}
    finally:
        agent.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Retoma intenção aprovada no Action Journal")
    parser.add_argument("intent_id", help="UUID da intenção aprovada")
    args = parser.parse_args()
    result = resume_approved_intent(args.intent_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


def list_approved_awaiting_execution(limit: int = 20) -> list[dict[str, Any]]:
    conn = _db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT intent_id, agent_id, action_type, description, created_at
                  FROM agent_actions
                 WHERE status = 'approved'
                   AND outcome IS NULL
                 ORDER BY created_at ASC
                 LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()