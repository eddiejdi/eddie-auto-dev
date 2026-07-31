"""Testes do mcp_tool_bridge — geração de schema, classificação de risco e,
principalmente, o invariante de que ferramentas travadas nunca executam
antes de uma aprovação (`status == "approved"`)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "misc" / "mcp_tool_bridge.py"


def _load_bridge():
    module_name = "mcp_tool_bridge_for_tests"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


bridge = _load_bridge()


# ── Descoberta de ferramentas / schema ──────────────────────────────────────


def test_discovers_36_tools_including_excluded():
    names = bridge.discovered_tool_names(include_excluded=True)
    assert len(names) == 36, sorted(names)


def test_excludes_governance_tools_from_model_visible_set():
    names = bridge.discovered_tool_names(include_excluded=False)
    assert names.isdisjoint(bridge.EXCLUDED_TOOLS)
    assert len(names) == 36 - len(bridge.EXCLUDED_TOOLS)


def test_schema_generation_matches_visible_tools():
    schemas = bridge.build_ollama_tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == bridge.discovered_tool_names(include_excluded=False)
    for s in schemas:
        assert s["type"] == "function"
        assert "parameters" in s["function"]
        assert s["function"]["parameters"].get("type") == "object"


def test_schema_includes_known_tool_with_correct_params():
    schemas = {s["function"]["name"]: s for s in bridge.build_ollama_tool_schemas()}
    secrets_get = schemas["secrets_get"]
    props = secrets_get["function"]["parameters"]["properties"]
    assert "name" in props
    assert "name" in secrets_get["function"]["parameters"]["required"]

    trading_summary = schemas["trading_summary"]
    props = trading_summary["function"]["parameters"]["properties"]
    assert "symbol" in props and "profile" in props
    # symbol/profile têm default -> não obrigatórios
    assert trading_summary["function"]["parameters"].get("required", []) == []


# ── Tabela de risco ──────────────────────────────────────────────────────


def test_tool_risk_table_exactly_matches_discovered_visible_tools():
    """Guarda de regressão: se homelab_mcp_server.py ganhar/perder ferramenta,
    este teste falha até alguém classificar/limpar TOOL_RISK explicitamente."""
    discovered = bridge.discovered_tool_names(include_excluded=False)
    classified = set(bridge.TOOL_RISK.keys())
    assert discovered == classified, (
        f"Descobertas mas não classificadas: {discovered - classified}; "
        f"Classificadas mas não existem mais: {classified - discovered}"
    )


def test_classify_unknown_tool_defaults_to_high(caplog):
    assert bridge.classify("tool_que_nao_existe_ainda") == "high"


@pytest.mark.parametrize(
    "tool_name,expected",
    [
        ("secrets_get", "critical"),
        ("secrets_list", "high"),
        ("db_execute_query", "high"),
        ("bus_publish", "high"),
        ("memory_store", "low"),
        ("memory_search", "none"),
        ("trading_summary", "none"),
        ("db_list_tables", "none"),
    ],
)
def test_classify_known_tools(tool_name, expected):
    assert bridge.classify(tool_name) == expected


@pytest.mark.parametrize(
    "tool_name,expected_gated",
    [
        ("secrets_get", True),
        ("db_execute_query", True),
        ("memory_store", False),
        ("trading_summary", False),
    ],
)
def test_is_gated(tool_name, expected_gated):
    assert bridge.is_gated(tool_name) is expected_gated


# ── Execução segura ──────────────────────────────────────────────────────


def test_execute_safe_calls_underlying_function_and_parses_json():
    mod = bridge._load_mcp_module()
    with patch.object(mod, "db_list_tables", return_value=json.dumps({"ok": True, "rows": []})) as fake:
        result = bridge.execute_safe("db_list_tables", {})
    fake.assert_called_once_with()
    assert result == {"ok": True, "rows": []}


def test_execute_safe_refuses_gated_tool():
    with pytest.raises(ValueError):
        bridge.execute_safe("secrets_get", {"name": "eddie/foo"})


# ── Caminho travado: nunca executa antes de aprovado (teste mais importante) ──


def test_gated_tool_never_executes_before_approval():
    """Se a aprovação nunca chega (fica sempre 'pending'), a ferramenta real
    jamais é chamada e o bridge resolve como 'expired' ao estourar o timeout."""
    mod = bridge._load_mcp_module()
    calls: list[tuple[str, object]] = []

    async def on_resolved(status, result):
        calls.append((status, result))

    with patch.object(mod, "secrets_get") as fake_secrets_get, \
         patch.object(mod, "intent_check_status", return_value=json.dumps({"ok": True, "status": "pending"})), \
         patch.object(bridge.asyncio, "sleep", new=AsyncMock(return_value=None)):
        asyncio.run(
            bridge.await_and_execute(
                "intent-x", "secrets_get", {"name": "eddie/foo"}, on_resolved,
                max_wait_seconds=0.001,
            )
        )

    fake_secrets_get.assert_not_called()
    assert calls and calls[0][0] == "expired"


def test_gated_tool_executes_only_after_approved():
    mod = bridge._load_mcp_module()
    calls: list[tuple[str, object]] = []

    async def on_resolved(status, result):
        calls.append((status, result))

    statuses = iter([
        json.dumps({"ok": True, "status": "pending"}),
        json.dumps({"ok": True, "status": "approved"}),
    ])

    with patch.object(mod, "secrets_get", return_value=json.dumps({"ok": True, "value": "shh"})) as fake_secrets_get, \
         patch.object(mod, "intent_check_status", side_effect=lambda intent_id: next(statuses)), \
         patch.object(mod, "intent_complete", return_value=json.dumps({"ok": True})) as fake_complete:

        async def run():
            await bridge.await_and_execute(
                "intent-y", "secrets_get", {"name": "eddie/foo"}, on_resolved,
            )

        # backoff schedule começa em 5s; patch pra teste não esperar de verdade
        with patch.object(bridge.asyncio, "sleep", new=AsyncMock(return_value=None)):
            asyncio.run(run())

    fake_secrets_get.assert_called_once_with(name="eddie/foo")
    fake_complete.assert_called_once()
    assert calls == [("approved", {"ok": True, "value": "shh"})]


def test_gated_tool_rejected_never_executes():
    mod = bridge._load_mcp_module()
    calls: list[tuple[str, object]] = []

    async def on_resolved(status, result):
        calls.append((status, result))

    with patch.object(mod, "secrets_get") as fake_secrets_get, \
         patch.object(mod, "intent_check_status", return_value=json.dumps({"ok": True, "status": "rejected"})):
        asyncio.run(bridge.await_and_execute("intent-z", "secrets_get", {"name": "eddie/foo"}, on_resolved))

    fake_secrets_get.assert_not_called()
    assert calls == [("rejected", None)]


def test_declare_gate_uses_classified_risk_level():
    mod = bridge._load_mcp_module()
    with patch.object(
        mod, "intent_declare",
        return_value=json.dumps({"ok": True, "intent_id": "intent-abc", "status": "pending"}),
    ) as fake_declare:
        intent_id = bridge.declare_gate("secrets_get", {"name": "eddie/foo"}, "quer ler um segredo")
    assert intent_id == "intent-abc"
    _, kwargs = fake_declare.call_args
    assert kwargs["risk_level"] == "critical"
    assert kwargs["target"] == "secrets_get"
