"""Métricas btc_rebuy_envelope_* no prometheus_exporter (2026-07-16).

O exporter espelha o último bloqueio de rebuy anotado pelo agente em
decisions.features (janela 30 min) — sem duplicar a matemática do envelope.
"""
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock psycopg2/secrets antes de importar o módulo (padrão do repo)
sys.modules.setdefault("psycopg2", MagicMock())
secrets_mock = types.ModuleType("secrets_helper")
secrets_mock.get_database_url = lambda: "postgresql://mock/mock"
sys.modules.setdefault("secrets_helper", secrets_mock)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

import prometheus_exporter  # noqa: E402


def _collector(symbol="BTC-USDT", profile="aggressive"):
    with patch.object(prometheus_exporter, "load_config", return_value={}):
        c = prometheus_exporter.MetricsCollector.__new__(prometheus_exporter.MetricsCollector)
    c.symbol = symbol
    c.profile = profile
    c.dsn = "postgresql://mock"
    return c


def test_envelope_metrics_from_latest_block_annotation():
    c = _collector()
    cur = MagicMock()
    now = time.time()
    cur.fetchone.return_value = ("decay", "63500.50", "64100.00", "6.25", now - 120)

    out = c._collect_rebuy_envelope(cur)

    assert out["rebuy_envelope_phase"] == 2
    assert out["rebuy_envelope_ceiling"] == 63500.50
    assert out["rebuy_envelope_raw_ceiling"] == 64100.00
    assert out["rebuy_envelope_elapsed_hours"] == 6.25
    assert 100 < out["rebuy_envelope_block_age_seconds"] < 140
    # Query filtra por symbol+profile e pelo block_reason do envelope
    sql = cur.execute.call_args.args[0]
    assert "buy_rebuy_lock_last_sell" in sql
    assert cur.execute.call_args.args[1] == ("BTC-USDT", "aggressive")


def test_envelope_metrics_zero_when_no_recent_block():
    c = _collector()
    cur = MagicMock()
    cur.fetchone.return_value = None

    out = c._collect_rebuy_envelope(cur)

    assert out["rebuy_envelope_phase"] == 0
    assert out["rebuy_envelope_ceiling"] == 0.0
    assert out["rebuy_envelope_block_age_seconds"] == 0.0


def test_envelope_metrics_grace_phase_and_bad_values_are_safe():
    c = _collector()
    cur = MagicMock()
    cur.fetchone.return_value = ("grace", None, None, None, None)

    out = c._collect_rebuy_envelope(cur)

    assert out["rebuy_envelope_phase"] == 1
    assert out["rebuy_envelope_ceiling"] == 0.0
    assert out["rebuy_envelope_elapsed_hours"] == 0.0


def test_envelope_metrics_never_raise_on_db_error():
    c = _collector()
    cur = MagicMock()
    cur.execute.side_effect = RuntimeError("db down")

    out = c._collect_rebuy_envelope(cur)

    assert out["rebuy_envelope_phase"] == 0  # falha → defaults, sem exceção
