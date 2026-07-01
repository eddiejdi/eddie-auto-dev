"""
Coordinator LangGraph — reimplementação do CoordinatorAgent em LangGraph.

Drop-in replacement para `run_coordinator_service.py` com adição de:
  - Checkpointing via PostgresSaver (resume após restart)
  - Governance: declare_intent → Action Journal
  - Shared Memory: store_memory após cada task bem-sucedida
  - Web search enriquecido como nó separado (time-travel debug individual)
  - Feature flag: COORDINATOR_VERSION=v2 para ativar

Flow do grafo::

    START → declare_intent → execute_dev → [success: store_memory → complete_intent → END]
                                         → [failed: enrich_and_retry → execute_dev]
                                         → [max_retries: complete_intent(failed) → END]

Interface com o bus (idêntica à v1)::

    Entrada:  REQUEST msg, target="CoordinatorAgent" | "agent_coordinator"
    Saída:    RESPONSE msg, source="CoordinatorAgent", target=msg.source
    Formato:  content = str({"success": bool, ...})

Env vars::
    COORDINATOR_VERSION     — v1 (default) | v2
    COORDINATOR_MAX_RETRIES — default 3
    RAG_API_URL             — URL da API RAG (opcional)
    DATABASE_URL            — obrigatório para checkpointer
"""
from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from typing import Literal, TypedDict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from langgraph.graph import StateGraph, START, END

from specialized_agents.langgraph_base import (
    AgentState,
    _resolve_db_url,
    _intent_declare,
    _intent_complete,
    _memory_store,
    _route_after_declare,
)

logger = logging.getLogger("dev_agent.coordinator_langgraph")

MAX_RETRIES = int(os.environ.get("COORDINATOR_MAX_RETRIES", "3"))


# ── State específico do coordinator ───────────────────────────────────────────


class CoordinatorState(TypedDict, total=False):
    # Identidade
    agent_id:    str
    action_type: str
    risk_level:  str
    thread_id:   str

    # Request
    description: str
    language:    str
    request_id:  str
    bus_source:  str  # agente que enviou o REQUEST

    # Governance
    intent_id:  str
    approval:   Literal["not_required", "pending", "approved", "rejected"]

    # Execução
    attempt:    int
    errors:     list
    dev_result: dict
    enriched:   bool  # web search já foi usado?

    # Output
    outcome:     str
    memory_fact: str
    error:       str
    status:      Literal["running", "done", "failed", "rejected"]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_dev_agent():
    from dev_agent.config import OLLAMA_HOST, OLLAMA_MODEL
    from dev_agent.agent import DevAgent
    return DevAgent(llm_url=OLLAMA_HOST, model=OLLAMA_MODEL)


def _build_search():
    try:
        from web_search import create_search_engine
        return create_search_engine()
    except Exception:
        return None


# ── Nodes ──────────────────────────────────────────────────────────────────────


def _node_declare_intent(state: CoordinatorState) -> CoordinatorState:
    intent_id = _intent_declare(
        agent_id    = state.get("agent_id", "coordinator_langgraph"),
        action_type = state.get("action_type", "coordinator_task"),
        description = state.get("description", "")[:500],
        target      = state.get("bus_source", "unknown"),
        risk_level  = state.get("risk_level", "low"),
    )
    return {**state, "intent_id": intent_id, "approval": "not_required", "status": "running"}


def _node_execute_dev(state: CoordinatorState) -> CoordinatorState:
    description = state.get("description", "")
    language    = state.get("language", "python")
    attempt     = state.get("attempt", 0)
    errors      = list(state.get("errors", []))

    try:
        dev_agent = _build_dev_agent()
        result    = dev_agent.develop(description, language)
    except Exception as exc:
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    if result.get("success"):
        outcome = (
            f"Task concluída após {attempt + 1} tentativa(s). "
            f"task_id={result.get('task_id', '?')}"
        )
        return {
            **state,
            "dev_result":  result,
            "attempt":     attempt + 1,
            "errors":      errors,
            "outcome":     outcome,
            "memory_fact": f"coordinator_langgraph: '{description[:120]}' → sucesso ({attempt + 1} tentativas)",
            "status":      "done",
        }

    err = result.get("error", "unknown_error")
    errors.append(err)
    logger.warning("[coordinator_langgraph] attempt=%d falhou: %s", attempt + 1, err[:200])
    return {
        **state,
        "dev_result": result,
        "attempt":    attempt + 1,
        "errors":     errors,
        "status":     "running",
    }


def _node_enrich_and_retry(state: CoordinatorState) -> CoordinatorState:
    """Enriquece a descrição com web search e incrementa tentativa."""
    description = state.get("description", "")
    enriched    = state.get("enriched", False)

    if not enriched:
        search = _build_search()
        if search:
            try:
                results   = search.search(description)
                extra     = "\n\nInformações encontradas na web:\n" + str(results)
                extra    += "\n\nUse essas informações para resolver o problema."
                description = description + extra
                logger.info("[coordinator_langgraph] Descrição enriquecida com web search")
            except Exception as exc:
                logger.warning("[coordinator_langgraph] Web search falhou: %s", exc)

    return {**state, "description": description, "enriched": True}


def _node_store_memory(state: CoordinatorState) -> CoordinatorState:
    fact = state.get("memory_fact") or state.get("outcome", "")
    if fact:
        try:
            _memory_store(
                fact     = fact,
                source   = "agent",
                tags     = ["coordinator_langgraph", state.get("status", "done")],
                agent_id = "coordinator_langgraph",
            )
        except Exception:
            pass
    return state


def _node_complete_intent(state: CoordinatorState) -> CoordinatorState:
    intent_id = state.get("intent_id")
    if not intent_id:
        return state
    status = state.get("status", "done")
    if status == "done":
        _intent_complete(intent_id, outcome=state.get("outcome", "ok"))
    else:
        errors = state.get("errors", [])
        err_summary = " | ".join(str(e)[:200] for e in errors[-3:])
        _intent_complete(intent_id, outcome="", error=err_summary or "max_retries exceeded")
    return state


def _node_fail(state: CoordinatorState) -> CoordinatorState:
    errors = state.get("errors", [])
    outcome = f"Falhou após {state.get('attempt', 0)} tentativa(s). Requer intervenção humana."
    return {**state, "status": "failed", "outcome": outcome}


# ── Routing ────────────────────────────────────────────────────────────────────


def _route_after_execute(state: CoordinatorState) -> str:
    if state.get("status") == "done":
        return "store_memory"
    attempt = state.get("attempt", 0)
    if attempt >= MAX_RETRIES:
        return "fail"
    if not state.get("enriched", False) and attempt >= 1:
        return "enrich_and_retry"
    return "execute_dev"


# ── Graph builder ──────────────────────────────────────────────────────────────


def _build_graph(checkpointer=None):
    builder = StateGraph(CoordinatorState)
    builder.add_node("declare_intent",   _node_declare_intent)
    builder.add_node("execute_dev",      _node_execute_dev)
    builder.add_node("enrich_and_retry", _node_enrich_and_retry)
    builder.add_node("store_memory",     _node_store_memory)
    builder.add_node("complete_intent",  _node_complete_intent)
    builder.add_node("fail",             _node_fail)

    builder.add_edge(START, "declare_intent")
    # declare_intent: coordinator tasks são sempre low-risk → vai direto para execute
    builder.add_edge("declare_intent",   "execute_dev")
    builder.add_conditional_edges(
        "execute_dev", _route_after_execute,
        {
            "store_memory":     "store_memory",
            "enrich_and_retry": "enrich_and_retry",
            "execute_dev":      "execute_dev",
            "fail":             "fail",
        }
    )
    builder.add_edge("enrich_and_retry", "execute_dev")
    builder.add_edge("store_memory",     "complete_intent")
    builder.add_edge("complete_intent",  END)
    builder.add_edge("fail",             "complete_intent")

    return builder.compile(checkpointer=checkpointer)


# ── Service runner ─────────────────────────────────────────────────────────────


class CoordinatorV2Service:
    """Long-running service que substitui run_coordinator_service.py."""

    def __init__(self):
        from langgraph.checkpoint.postgres import PostgresSaver
        self._cp_ctx  = PostgresSaver.from_conn_string(_resolve_db_url())
        self._saver   = self._cp_ctx.__enter__()
        self._saver.setup()
        self._graph   = _build_graph(checkpointer=self._saver)
        self._version = os.environ.get("COORDINATOR_VERSION", "v2")

    def close(self):
        ctx = getattr(self, "_cp_ctx", None)
        if ctx:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass

    def handle_message(self, msg) -> None:
        """Callback registrado no AgentCommunicationBus."""
        from specialized_agents.agent_communication_bus import (
            AgentCommunicationBus, MessageType,
        )
        bus = AgentCommunicationBus()

        if msg.message_type.value != "request":
            return
        if msg.target not in ("CoordinatorAgent", "agent_coordinator"):
            return

        import uuid
        request_id = msg.metadata.get("request_id", msg.id)
        thread_id  = f"coord_{request_id}"
        logger.info("[coordinator_langgraph] request de %s (thread=%s)", msg.source, thread_id[:24])

        initial: CoordinatorState = {
            "agent_id":    "coordinator_langgraph",
            "action_type": "coordinator_task",
            "risk_level":  "low",
            "description": msg.content,
            "language":    msg.metadata.get("language", "python"),
            "request_id":  request_id,
            "bus_source":  msg.source,
            "thread_id":   thread_id,
            "attempt":     0,
            "errors":      [],
            "enriched":    False,
            "status":      "running",
        }

        config = {"configurable": {"thread_id": thread_id}}
        try:
            for _ in self._graph.stream(initial, config):
                pass
            final = self._graph.get_state(config).values
            result_dict = {
                "success":    final.get("status") == "done",
                "outcome":    final.get("outcome", ""),
                "iterations": final.get("attempt", 0),
                "errors":     final.get("errors", []),
                "thread_id":  thread_id,
            }
            if final.get("status") != "done":
                result_dict["requires_user"] = True
        except Exception as exc:
            logger.error("[coordinator_langgraph] erro no grafo: %s", exc)
            result_dict = {"success": False, "error": str(exc), "requires_user": True}

        bus.publish(
            message_type = MessageType.RESPONSE,
            source       = "CoordinatorAgent",
            target       = msg.source,
            content      = str(result_dict),
            metadata     = {"request_id": request_id, "coordinator_version": "v2"},
        )

    def run_forever(self) -> None:
        """Bloqueia até SIGTERM/SIGINT."""
        import signal

        from specialized_agents.agent_communication_bus import AgentCommunicationBus
        bus = AgentCommunicationBus()
        bus.recording = True
        bus.subscribe(self.handle_message)

        logger.info("[coordinator_langgraph] Listening on AgentCommunicationBus (version=v2)...")

        stop = False

        def _sig(sig, frame):
            nonlocal stop
            stop = True

        signal.signal(signal.SIGTERM, _sig)
        signal.signal(signal.SIGINT,  _sig)

        try:
            while not stop:
                time.sleep(1)
        finally:
            bus.unsubscribe(self.handle_message)
            self.close()
            logger.info("[coordinator_langgraph] Encerrado.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    svc = CoordinatorV2Service()
    svc.run_forever()


if __name__ == "__main__":
    main()
