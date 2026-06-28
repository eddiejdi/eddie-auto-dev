"""
Base template for homelab agents built with LangGraph.

Provides a governance-integrated graph skeleton with:
  - declare_intent  → registra intenção no Action Journal (risk ≥ medium → aprovação Telegram)
  - await_approval  → interrupt node; retomado após aprovação via LangGraph checkpointer
  - execute         → lógica do agente (override _execute_work)
  - store_memory    → persiste resultado na memória compartilhada
  - complete_intent → fecha o registro no Action Journal

Usage
-----
Subclasse mínima::

    class MyAgent(HomelabAgent):
        AGENT_ID   = "my_agent"
        ACTION_TYPE = "my_action"
        RISK_LEVEL  = "low"

        def _describe_work(self, state: AgentState) -> str:
            return f"processar {state['target']}"

        def _execute_work(self, state: AgentState) -> dict:
            # faz o trabalho; retorna {"outcome": "...", "memory_fact": "..."}
            ...

Para usar o checkpoint PostgreSQL (resume após reinício/aprovação)::

    agent = MyAgent()
    # primeira execução
    result = agent.run(target="foo", description="processar foo")
    # se parou em await_approval, retome com:
    result = agent.resume(thread_id=result["thread_id"])

Env vars
--------
    DATABASE_URL        — PostgreSQL para checkpointer e Action Journal
    ANTHROPIC_API_KEY   — opcional; só se o agente usar ChatAnthropic
    CHROMA_DB_PATH      — ChromaDB path (default /home/homelab/myClaude/chroma_db)
"""
from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from typing import Any, Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

# ── State ─────────────────────────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    # Inputs
    agent_id:    str
    action_type: str
    target:      str
    description: str
    risk_level:  str
    extra:       dict

    # Internal governance
    intent_id:   str
    approval:    Literal["pending", "approved", "rejected", "not_required"]
    thread_id:   str

    # Results
    outcome:     str
    memory_fact: str
    error:       str
    status:      Literal["running", "done", "failed", "rejected"]


# ── Governance helpers ─────────────────────────────────────────────────────────


def _mcp_rpc(tool: str, **kwargs) -> dict:
    """Chama um MCP tool via JSON-RPC direto ao homelab_mcp_server.

    Alternativa simplificada: importa o módulo diretamente.
    """
    import importlib.util
    _HERE = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "homelab_mcp_server",
        os.path.join(os.path.dirname(_HERE), "scripts", "homelab_mcp_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, tool)
    result = fn(**kwargs)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw": result}
    return result


def _resolve_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        for path in ["/etc/default/eddie-common"]:
            try:
                for line in open(path).read().splitlines():
                    if line.startswith("DATABASE_URL="):
                        db_url = line.split("=", 1)[1].strip()
                        break
            except (FileNotFoundError, PermissionError):
                pass
    return db_url


def _db_connect():
    """Conexão psycopg2 para operações do Action Journal (INSERT/UPDATE)."""
    import psycopg2
    return psycopg2.connect(_resolve_db_url())


def _db_connect_pg3(autocommit: bool = False):
    """Conexão psycopg3 para o LangGraph PostgresSaver."""
    import psycopg
    return psycopg.connect(_resolve_db_url(), autocommit=autocommit)


def _intent_declare(agent_id: str, action_type: str, description: str,
                    target: str, risk_level: str) -> str:
    """Insere na tabela agent_actions; retorna intent_id (UUID)."""
    intent_id = str(uuid.uuid4())
    conn = _db_connect()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO agent_actions
                    (intent_id, agent_id, action_type, description, target, risk_level, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                RETURNING intent_id
            """, (intent_id, agent_id, action_type, description, target, risk_level))
    conn.close()
    return intent_id


def _intent_check(intent_id: str) -> str:
    """Retorna o status atual da intenção."""
    conn = _db_connect()
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM agent_actions WHERE intent_id = %s", (intent_id,))
        row = cur.fetchone()
    conn.close()
    return row[0] if row else "unknown"


def _intent_complete(intent_id: str, outcome: str, error: str | None = None) -> None:
    """Fecha o registro com outcome/error_detail."""
    conn = _db_connect()
    new_status = "failed" if error else "done"
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE agent_actions
                   SET status = %s,
                       outcome = %s,
                       error_detail = %s,
                       resolved_at = NOW()
                 WHERE intent_id = %s
            """, (new_status, outcome[:2000] if outcome else None,
                  error[:1000] if error else None, intent_id))
    conn.close()


def _memory_store(fact: str, source: str, tags: list[str], agent_id: str) -> str:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_HERE))
    from tools.memory_layer.agent_memory import store
    return store(fact, source=source, tags=tags, agent_id=agent_id)


# ── Nodes ──────────────────────────────────────────────────────────────────────


def _node_declare_intent(state: AgentState) -> AgentState:
    intent_id = _intent_declare(
        agent_id=state["agent_id"],
        action_type=state["action_type"],
        description=state.get("description", ""),
        target=state.get("target", ""),
        risk_level=state.get("risk_level", "low"),
    )
    risk = state.get("risk_level", "low")
    approval = "not_required" if risk == "low" else "pending"
    return {**state, "intent_id": intent_id, "approval": approval, "status": "running"}


def _node_await_approval(state: AgentState) -> AgentState:
    """Interrupt node — LangGraph pausa aqui até o checkpointer ser retomado.

    Quando o approval-gateway aprova/rejeita a intenção no DB, o agente é
    retomado via agent.resume(thread_id=...) e este nó relê o status.
    """
    intent_id = state["intent_id"]
    # Se já foi resolvido externamente (resume após aprovação), propaga.
    db_status = _intent_check(intent_id)
    if db_status == "approved":
        return {**state, "approval": "approved"}
    if db_status in ("rejected", "expired"):
        return {**state, "approval": "rejected", "status": "rejected"}
    # Ainda pending: o interrupt é sinalizado para o runner pelo status
    return {**state, "approval": "pending"}


def _node_execute(state: AgentState, execute_fn) -> AgentState:
    """Delega para a função de execução concreta do agente."""
    try:
        result = execute_fn(state)
        outcome = result.get("outcome", "ok")
        memory_fact = result.get("memory_fact", "")
        return {**state, "outcome": outcome, "memory_fact": memory_fact, "status": "done"}
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}"
        return {**state, "error": err, "status": "failed"}


def _node_store_memory(state: AgentState) -> AgentState:
    fact = state.get("memory_fact") or state.get("outcome", "")
    if fact:
        try:
            _memory_store(
                fact=fact,
                source="agent",
                tags=[state.get("action_type", ""), state.get("risk_level", "")],
                agent_id=state.get("agent_id", "unknown"),
            )
        except Exception:
            pass  # memória é best-effort
    return state


def _node_complete_intent(state: AgentState) -> AgentState:
    intent_id = state.get("intent_id")
    if intent_id:
        _intent_complete(
            intent_id=intent_id,
            outcome=state.get("outcome", ""),
            error=state.get("error"),
        )
    return state


def _node_reject(state: AgentState) -> AgentState:
    intent_id = state.get("intent_id")
    if intent_id:
        _intent_complete(intent_id=intent_id, outcome="Rejeitado pelo operador", error=None)
    return {**state, "status": "rejected"}


# ── Route helpers ──────────────────────────────────────────────────────────────


def _route_after_declare(state: AgentState) -> str:
    return "await_approval" if state.get("approval") == "pending" else "execute"


def _route_after_await(state: AgentState) -> str:
    approval = state.get("approval", "pending")
    if approval == "approved":
        return "execute"
    if approval == "rejected":
        return "reject"
    return "await_approval"  # ainda pending — interrupt


# ── HomelabAgent base class ────────────────────────────────────────────────────


class HomelabAgent:
    """Subclasse esta classe para criar um novo agente com governança integrada.

    Atributos obrigatórios::

        AGENT_ID    = "meu_agente"       # identificador único
        ACTION_TYPE = "tipo_de_acao"     # ex: "ltfs_rotate", "deploy_service"
        RISK_LEVEL  = "low"              # low | medium | high | critical

    Métodos a implementar::

        _describe_work(state) → str      # descrição humana da intenção
        _execute_work(state)  → dict     # {"outcome": "...", "memory_fact": "..."}
    """

    AGENT_ID:    str = "homelab_agent"
    ACTION_TYPE: str = "generic_action"
    RISK_LEVEL:  str = "low"

    # Interrupt: se True, para no nó await_approval aguardando retomada manual.
    # HomelabAgent define True por padrão para risk ≥ medium.
    INTERRUPT_ON_APPROVAL: bool = True

    def __init__(self):
        self._graph = None
        self._checkpointer = None

    # ── Override these ─────────────────────────────────────────────────────────

    def _describe_work(self, state: AgentState) -> str:
        return state.get("description", f"{self.ACTION_TYPE} em {state.get('target', '?')}")

    def _execute_work(self, state: AgentState) -> dict:
        raise NotImplementedError("Implemente _execute_work na sua subclasse.")

    # ── Graph construction ─────────────────────────────────────────────────────

    def _build_graph(self):
        execute_fn = self._execute_work

        def declare(s):  return _node_declare_intent(s)
        def await_ap(s): return _node_await_approval(s)
        def execute(s):  return _node_execute(s, execute_fn)
        def memory(s):   return _node_store_memory(s)
        def complete(s): return _node_complete_intent(s)
        def reject(s):   return _node_reject(s)

        builder = StateGraph(AgentState)
        builder.add_node("declare_intent",  declare)
        builder.add_node("await_approval",  await_ap)
        builder.add_node("execute",         execute)
        builder.add_node("store_memory",    memory)
        builder.add_node("complete_intent", complete)
        builder.add_node("reject",          reject)

        builder.add_edge(START, "declare_intent")
        builder.add_conditional_edges("declare_intent", _route_after_declare,
                                      {"await_approval": "await_approval",
                                       "execute": "execute"})
        builder.add_conditional_edges("await_approval", _route_after_await,
                                      {"execute": "execute",
                                       "reject": "reject",
                                       "await_approval": END})  # pause until resume
        builder.add_edge("execute",         "store_memory")
        builder.add_edge("store_memory",    "complete_intent")
        builder.add_edge("complete_intent", END)
        builder.add_edge("reject",          END)

        interrupts = ["await_approval"] if self.INTERRUPT_ON_APPROVAL else []
        return builder.compile(
            checkpointer=self._checkpointer,
            interrupt_before=interrupts,
        )

    def _get_checkpointer(self):
        if self._checkpointer is None:
            # from_conn_string é um context manager; __enter__ retorna o PostgresSaver real
            self._cp_ctx = PostgresSaver.from_conn_string(_resolve_db_url())
            saver = self._cp_ctx.__enter__()
            saver.setup()
            self._checkpointer = saver
        return self._checkpointer

    def close(self):
        """Libera recursos do checkpointer. Chamar ao encerrar o agente."""
        ctx = getattr(self, "_cp_ctx", None)
        if ctx is not None:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass
        self._checkpointer = None
        self._graph = None
        self._cp_ctx = None

    def _get_graph(self):
        if self._graph is None:
            self._checkpointer = self._get_checkpointer()
            self._graph = self._build_graph()
        return self._graph

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(
        self,
        target: str = "",
        description: str = "",
        extra: dict | None = None,
        thread_id: str | None = None,
    ) -> AgentState:
        """Inicia uma nova execução (ou retoma um thread existente).

        Retorna o estado final. Se parado em await_approval, retorna com
        status='running' e approval='pending'; use resume(thread_id) para continuar.
        """
        tid = thread_id or str(uuid.uuid4())
        initial: AgentState = {
            "agent_id":    self.AGENT_ID,
            "action_type": self.ACTION_TYPE,
            "risk_level":  self.RISK_LEVEL,
            "target":      target,
            "description": description or self._describe_work({"target": target}),  # type: ignore[arg-type]
            "extra":       extra or {},
            "thread_id":   tid,
            "status":      "running",
        }
        config = {"configurable": {"thread_id": tid}}
        graph  = self._get_graph()
        final  = None
        for chunk in graph.stream(initial, config):
            final = chunk
        state = graph.get_state(config).values
        state["thread_id"] = tid
        return state  # type: ignore[return-value]

    def resume(self, thread_id: str) -> AgentState:
        """Retoma um thread pausado em await_approval.

        Usado depois que o approval-gateway aprovou a intenção no DB.
        """
        config = {"configurable": {"thread_id": thread_id}}
        graph  = self._get_graph()
        # Lê estado salvo, atualiza approval se DB diz approved
        saved = graph.get_state(config).values
        intent_id = saved.get("intent_id", "")
        if intent_id:
            db_status = _intent_check(intent_id)
            if db_status == "approved":
                graph.update_state(config, {"approval": "approved"})
            elif db_status in ("rejected", "expired"):
                graph.update_state(config, {"approval": "rejected"})
        for _ in graph.stream(None, config):
            pass
        state = graph.get_state(config).values
        state["thread_id"] = thread_id
        return state  # type: ignore[return-value]

    def get_history(self, thread_id: str) -> list[dict]:
        """Retorna o histórico de estados do thread (time-travel debug)."""
        config = {"configurable": {"thread_id": thread_id}}
        graph  = self._get_graph()
        history = []
        for state in graph.get_state_history(config):
            history.append({
                "step":      state.metadata.get("step"),
                "next":      list(state.next),
                "values":    {k: v for k, v in state.values.items()
                              if k not in ("extra",)},
                "created_at": state.created_at,
            })
        return history
