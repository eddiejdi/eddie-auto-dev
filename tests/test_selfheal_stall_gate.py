"""Gate determinístico de stall no trading_selfheal_exporter (fix 2026-07-16).

O LLM (Ollama) só pode ser consultado quando a idade da última decisão excede
STALL_THRESHOLD; abaixo do gate, o agente é saudável por definição — o LLM
fraco marcava stalled com decisões frescas (62 restarts falsos/dia no USDT-BRL).
"""
import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


def load_module():
    os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/btc_trading")
    sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *_a, **_k: None))
    path = Path(__file__).resolve().parents[1] / "grafana" / "exporters" / "trading_selfheal_exporter.py"
    spec = importlib.util.spec_from_file_location("trading_selfheal_stall_gate_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_checker(mod, age_seconds, ollama_calls):
    agent = mod.TradingAgentDef(
        symbol="USDT-BRL",
        profile="aggressive",
        systemd_unit="crypto-agent@USDT_BRL_aggressive",
        exporter_port=9120,
        config_file="config_USDT_BRL_aggressive.json",
        expected_process="trading_agent.py.*USDT_BRL_aggressive",
    )
    checker = mod.AgentHealthChecker([agent], pg_dsn="postgresql://mock")
    checker.check_systemd_active = lambda unit: True
    checker.check_process = lambda pattern: True
    checker.check_runtime_integrity = lambda a, s: True
    checker.get_block_reason_coverage = lambda a, minutes=15: 1.0
    checker.get_last_decision_age = lambda symbol, profile="": age_seconds

    def fake_ollama(metric_id, age, reasons):
        ollama_calls.append((metric_id, age))
        return (0.95, "LLM alucinando stalled")  # pior caso: LLM sempre diz stalled

    mod.analyze_stall_with_ollama = fake_ollama
    return checker, agent.metric_id


def test_fresh_decisions_never_consult_llm_and_stay_healthy():
    """Idade abaixo do gate: LLM NÃO é chamado e o agente é saudável,
    mesmo que o LLM (se consultado) dissesse stalled com 95%."""
    mod = load_module()
    calls = []
    checker, agent_id = _make_checker(mod, age_seconds=30.0, ollama_calls=calls)

    healthy = checker.check_agent(agent_id)

    assert healthy is True
    assert calls == []  # gate determinístico: LLM nunca consultado
    state = checker.states[agent_id]
    assert state.stalled is False
    assert state.ollama_stall_confidence == 0.0
    assert "determinístico" in state.ollama_reasoning


def test_stale_decisions_consult_llm_beyond_gate():
    """Idade acima do gate: LLM é consultado e pode confirmar o stall."""
    mod = load_module()
    calls = []
    age = mod.STALL_THRESHOLD + 600
    checker, agent_id = _make_checker(mod, age_seconds=age, ollama_calls=calls)

    healthy = checker.check_agent(agent_id)

    assert healthy is False
    assert len(calls) == 1 and calls[0][1] == age
    assert checker.states[agent_id].stalled is True


def test_age_exactly_at_threshold_is_healthy():
    """Idade == threshold não passa do gate (> estrito)."""
    mod = load_module()
    calls = []
    checker, agent_id = _make_checker(
        mod, age_seconds=float(mod.STALL_THRESHOLD), ollama_calls=calls)

    assert checker.check_agent(agent_id) is True
    assert calls == []


def test_decision_age_query_uses_profile_filter():
    """get_last_decision_age filtra por profile quando o agente tem um."""
    mod = load_module()
    agent = mod.TradingAgentDef(
        symbol="USDT-BRL",
        profile="conservative",
        systemd_unit="crypto-agent@USDT_BRL_conservative",
        exporter_port=9121,
        config_file="config_USDT_BRL_conservative.json",
        expected_process="trading_agent.py.*USDT_BRL_conservative",
    )
    checker = mod.AgentHealthChecker([agent], pg_dsn="postgresql://mock")
    cur = MagicMock()
    cur.fetchone.return_value = (1000.0,)
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.closed = False
    checker._pg_conn = conn
    checker._ensure_pg_conn = lambda: None

    checker.get_last_decision_age("USDT-BRL", "conservative")

    executed_sql = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    assert "profile=%s" in executed_sql
