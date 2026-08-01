#!/usr/bin/env python3
"""Ponte entre um modelo Ollama com tool-calling e as ferramentas do
`scripts/homelab_mcp_server.py` (MCP server "homelab").

Sem dependência de WhatsApp/WAHA — pensado para ser testável isolado e
reutilizável por qualquer outra superfície (ex: um futuro bot Telegram).

Responsabilidades:
  - Carregar `homelab_mcp_server.py` em processo (mesmo padrão já usado por
    `specialized_agents/langgraph_base.py::_mcp_rpc`), uma única vez.
  - Gerar o schema de ferramentas no formato function-calling do Ollama a
    partir do `FastMCP._tool_manager` do módulo carregado (fonte única de
    verdade — não é escrito à mão, então não pode divergir das ferramentas
    reais).
  - Classificar cada ferramenta por risco (`TOOL_RISK`) e decidir se pode
    executar na hora ou precisa passar pela trava de aprovação (Telegram,
    via a camada de governança já existente: intent_declare/intent_check_status).
  - Fazer o polling de aprovação com backoff e executar a ferramenta real
    somente depois de `approved`.

Ver plano: /home/edenilson/.claude/plans/hazy-chasing-balloon.md
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("mcp_tool_bridge")

_HERE = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVER_PATH = os.path.join(os.path.dirname(_HERE), "homelab_mcp_server.py")

# Ferramentas de governança — plumbing da própria trava, nunca expostas ao
# modelo (ele nunca deve "decidir" chamar intent_declare/intent_complete
# diretamente; quem chama é esta bridge, em torno da ferramenta real).
EXCLUDED_TOOLS: frozenset[str] = frozenset(
    {"intent_declare", "intent_check_status", "intent_complete"}
)

# Classificação de risco por ferramenta (risk_level aceito por intent_declare:
# none | low | medium | high | critical). Tabela estática — risco é decisão
# humana, não algo para inferir de assinatura de função.
#
# memory_store fica "low" (ungated) deliberadamente: blast radius é local
# (ChromaDB), dedupado por hash, com TTL opcional, e o próprio repo já trata
# escrita de memória como bookkeeping best-effort sem gate em
# specialized_agents/langgraph_base.py::_node_store_memory. Gatear cada
# chamada de memory_store tornaria o assistente irritante de usar para a
# funcionalidade mais básica de conversa.
TOOL_RISK: dict[str, str] = {
    # SAFE — leitura, sem efeito colateral, executa na hora
    "bus_health": "none",
    "bus_get_messages": "none",
    "bus_search_by_agent": "none",
    "api_health": "none",
    "api_events_list": "none",
    "api_events_get": "none",
    "db_list_tables": "none",
    "db_describe_table": "none",
    "db_active_events": "none",
    "journal_query": "none",
    "memory_search": "none",
    "trading_performance": "none",
    "trading_recent_trades": "none",
    "trading_positions": "none",
    "trading_market_state": "none",
    "trading_decisions": "none",
    "trading_candles": "none",
    "trading_ai_controls": "none",
    "trading_ai_plan": "none",
    "trading_ai_window": "none",
    "trading_news_sentiment": "none",
    "trading_learning_stats": "none",
    "trading_summary": "none",
    # code_read_file/code_list_files só leem dentro do sandbox de
    # generated/integrations/ — sem efeito colateral, mesma classe de risco
    # das outras leituras.
    "code_read_file": "none",
    "code_list_files": "none",
    # LOW — grava, mas blast radius local/reversível/best-effort
    "memory_store": "low",
    # HIGH — escreve em sistema externo, expõe existência de credenciais,
    # ou executa SQL arbitrário (mesmo com guardrails de app)
    "secrets_list": "high",
    "secrets_health": "high",
    "api_auth_login": "high",
    "bus_publish": "high",
    "bus_record_result": "high",
    "api_events_create": "high",
    "api_checkins_create": "high",
    "db_execute_query": "high",
    # code_write_file grava arquivo em disco (sandboxed, mas ainda assim
    # conteúdo gerado por LLM sem revisão prévia) — exige aprovação.
    "code_write_file": "high",
    # CRITICAL — expõe valor de credencial
    "secrets_get": "critical",
}

# Ferramentas com side-effect ficam pendentes de aprovação humana; o resto
# executa direto. Mantido em paridade com `_AUTO_APPROVE_LEVELS` do
# homelab_mcp_server.py (none/low auto-aprovam).
_AUTO_EXECUTE_LEVELS = frozenset({"none", "low"})

# Backoff de polling (segundos) — o último valor se repete até o timeout.
_BACKOFF_SCHEDULE = (5, 5, 10, 15, 30)

DEFAULT_AGENT_ID = "whatsapp-bot"

_module_cache: Any = None


def _load_mcp_module() -> Any:
    """Importa scripts/homelab_mcp_server.py como módulo Python, uma vez.

    Mesmo padrão de `specialized_agents/langgraph_base.py::_mcp_rpc`, mas
    cacheado — o módulo faz resolução de env/DSN em nível de módulo
    (`_db_url_cache`, `_trading_db_url_cache`) que deve persistir durante o
    tempo de vida do processo do bot, não ser refeita a cada chamada.
    """
    global _module_cache
    if _module_cache is not None:
        return _module_cache
    spec = importlib.util.spec_from_file_location("homelab_mcp_server", _MCP_SERVER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {_MCP_SERVER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _module_cache = mod
    return mod


def _all_tools(mod: Any) -> dict[str, Any]:
    """Retorna {nome: Tool} de todas as ferramentas registradas no FastMCP."""
    return {t.name: t for t in mod.mcp._tool_manager.list_tools()}


def discovered_tool_names(include_excluded: bool = False) -> set[str]:
    """Nomes de ferramentas descobertas via introspecção do FastMCP.

    Usado por testes para garantir que TOOL_RISK não fica desatualizado
    quando homelab_mcp_server.py ganha/perde ferramentas.
    """
    mod = _load_mcp_module()
    names = set(_all_tools(mod).keys())
    if not include_excluded:
        names -= EXCLUDED_TOOLS
    return names


def classify(tool_name: str) -> str:
    """Risk level de uma ferramenta. Fail-safe: desconhecida => 'high'."""
    risk = TOOL_RISK.get(tool_name)
    if risk is None:
        logger.warning(
            "Ferramenta MCP '%s' sem classificação de risco em TOOL_RISK — "
            "tratando como 'high' (nunca auto-executa por padrão).",
            tool_name,
        )
        return "high"
    return risk


def is_gated(tool_name: str) -> bool:
    return classify(tool_name) not in _AUTO_EXECUTE_LEVELS


def build_ollama_tool_schemas() -> list[dict]:
    """Gera o array `tools=` no formato function-calling do Ollama.

    Fonte única de verdade: introspecção do FastMCP (`t.parameters` já é um
    JSON-schema válido gerado a partir da assinatura real da função).
    Exclui ferramentas de governança (EXCLUDED_TOOLS).
    """
    mod = _load_mcp_module()
    schemas = []
    for name, tool in sorted(_all_tools(mod).items()):
        if name in EXCLUDED_TOOLS:
            continue
        description = (tool.description or "").strip()
        # primeiro parágrafo do docstring (antes da primeira linha em branco)
        description = description.split("\n\n", 1)[0].strip()
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": tool.parameters,
                },
            }
        )
    return schemas


def _call_tool(tool_name: str, kwargs: dict) -> Any:
    """Chama a função real da ferramenta e faz parse do retorno JSON-string.

    Usa `getattr(mod, tool_name)` (lookup por nome no módulo) em vez do
    `tool.fn` cacheado pelo FastMCP — o `Tool.fn` captura a referência da
    função no momento da decoração, então testes que fazem
    `patch.object(mod, tool_name, ...)` não teriam efeito se chamássemos
    `tool.fn` diretamente. Mesmo padrão de
    `specialized_agents/langgraph_base.py::_mcp_rpc`.
    """
    mod = _load_mcp_module()
    if tool_name not in _all_tools(mod):
        raise KeyError(f"Ferramenta MCP desconhecida: {tool_name}")
    fn = getattr(mod, tool_name)
    result = fn(**kwargs)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw": result}
    return result


def execute_safe(tool_name: str, kwargs: dict) -> Any:
    """Executa uma ferramenta 'none'/'low' imediatamente, sem trava.

    Levanta ValueError se a ferramenta exigir aprovação — uso incorreto do
    caller, não deveria acontecer se `is_gated` foi checado antes.
    """
    if is_gated(tool_name):
        raise ValueError(
            f"'{tool_name}' requer aprovação (risk={classify(tool_name)}); "
            "use declare_gate()+await_and_execute(), não execute_safe()."
        )
    return _call_tool(tool_name, kwargs)


def declare_gate(
    tool_name: str,
    kwargs: dict,
    description: str,
    agent_id: str = DEFAULT_AGENT_ID,
) -> str:
    """Declara a intenção de chamar uma ferramenta arriscada.

    Retorna o intent_id (para poll manual) — o caminho normal é passar
    direto para `await_and_execute`.
    """
    mod = _load_mcp_module()
    risk = classify(tool_name)
    context = json.dumps(kwargs, ensure_ascii=False, default=str)[:4000]
    raw = mod.intent_declare(
        agent_id=agent_id,
        action_type="other",
        description=description,
        target=tool_name,
        risk_level=risk,
        context=context,
    )
    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(f"intent_declare falhou para '{tool_name}': {data}")
    return data["intent_id"]


async def await_and_execute(
    intent_id: str,
    tool_name: str,
    kwargs: dict,
    on_resolved: Callable[[str, Any], Awaitable[None]],
    max_wait_seconds: Optional[float] = None,
) -> None:
    """Faz polling de `intent_check_status` até approved/rejected/expired.

    Em `approved`, executa a ferramenta real e chama `intent_complete`.
    Chama `on_resolved(status, result_ou_erro)` exatamente uma vez ao final
    (status ∈ approved|rejected|expired|error). Nunca deixa exceção subir —
    erros inesperados também resolvem via `on_resolved("error", ...)`.
    """
    mod = _load_mcp_module()
    if max_wait_seconds is None:
        intent_exp_min = int(os.environ.get("INTENT_EXP_MIN", "10"))
        max_wait_seconds = intent_exp_min * 60 + 60  # margem sobre a expiração do gateway

    start = time.monotonic()
    step = 0
    try:
        while True:
            if time.monotonic() - start > max_wait_seconds:
                logger.info("intent_id=%s expirou no timeout local do bridge", intent_id)
                await on_resolved("expired", None)
                return

            raw = mod.intent_check_status(intent_id)
            data = json.loads(raw)
            if not data.get("ok"):
                logger.error("intent_check_status falhou para %s: %s", intent_id, data)
                await on_resolved("error", data.get("error", "erro desconhecido"))
                return

            status = data.get("status")
            if status == "approved":
                try:
                    result = _call_tool(tool_name, kwargs)
                    outcome = json.dumps(result, ensure_ascii=False, default=str)[:2000]
                    mod.intent_complete(intent_id=intent_id, outcome=outcome, success=True)
                    await on_resolved("approved", result)
                except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha da ferramenta
                    logger.exception("Erro executando '%s' após aprovação (intent_id=%s)", tool_name, intent_id)
                    mod.intent_complete(
                        intent_id=intent_id,
                        outcome="Falha ao executar após aprovação",
                        success=False,
                        error_detail=str(exc),
                    )
                    await on_resolved("error", str(exc))
                return

            if status in ("rejected", "expired"):
                await on_resolved(status, None)
                return

            delay = _BACKOFF_SCHEDULE[min(step, len(_BACKOFF_SCHEDULE) - 1)]
            step += 1
            await asyncio.sleep(delay)
    except Exception as exc:  # noqa: BLE001 - tarefa fire-and-forget nunca pode morrer silenciosa
        logger.exception("Erro inesperado no polling de aprovação intent_id=%s", intent_id)
        try:
            await on_resolved("error", str(exc))
        except Exception:
            logger.exception("on_resolved também falhou para intent_id=%s", intent_id)
