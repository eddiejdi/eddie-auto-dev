#!/usr/bin/env python3
"""Regressões para o log de chamadas ao LLM (dataset de fine-tuning).

Cobre:
  - TrainingDatabase.record_llm_call / get_llm_calls / prune_llm_calls
    (persistência em btc.llm_calls, com um pool de conexão falso).
  - TradingAgent._record_llm_call é best-effort: uma falha do DB NUNCA
    propaga para o caminho de decisão de trading.
"""

from pathlib import Path
import json
import os
import sys
import types

import pytest

# DSN sem credenciais — nenhum teste abre conexão real (pool é falso).
_TEST_DSN = "postgresql://localhost/test"
os.environ.setdefault("DATABASE_URL", _TEST_DSN)


def _force_real_module(name: str) -> None:
    """Garante que sys.modules[name] é o módulo REAL instalado, não um stub.

    Testes vizinhos instalam numpy/psycopg2 falsos via ``setdefault`` quando o
    real ainda não foi importado. training_db precisa dos reais (isinstance com
    np.floating, psycopg2.extras.RealDictCursor). Como numpy e psycopg2 são
    dependências reais de CI, forçamos o real aqui. Ver memória
    feedback_test_module_pollution.

    Sinal de "real": módulo com ``__file__`` string (stubs via types.ModuleType
    têm __file__=None; MagicMock nem é ModuleType). Também purga submódulos —
    um psycopg2 mock pode ter ``extras`` sem RealDictCursor.
    """
    mod = sys.modules.get(name)
    is_real = (
        isinstance(mod, types.ModuleType)
        and isinstance(getattr(mod, "__file__", None), str)
    )
    if not is_real:
        for key in [k for k in list(sys.modules) if k == name or k.startswith(name + ".")]:
            del sys.modules[key]
        __import__(name)


_force_real_module("numpy")
_force_real_module("psycopg2")
import psycopg2.extras  # noqa: E402,F401  (garante submódulo real carregado)
import psycopg2.pool    # noqa: E402,F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

# Garante o training_db REAL (outros testes podem ter stubado).
sys.modules.pop("training_db", None)
from training_db import TrainingDatabase  # noqa: E402


class _FakeCursor:
    """Cursor falso que grava (sql, params) e devolve respostas programáveis."""

    def __init__(self, log, fetchone_val=None, fetchall_val=None, rowcount=0):
        self._log = log
        self._fetchone_val = fetchone_val
        self._fetchall_val = fetchall_val or []
        self.rowcount = rowcount

    def execute(self, sql, params=None):
        self._log.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._fetchone_val

    def fetchall(self):
        return self._fetchall_val

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = False

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def getconn(self):
        return self._conn

    def putconn(self, conn):
        pass


def _make_db(cursor):
    """Instancia TrainingDatabase sem tocar no Postgres real."""
    db = TrainingDatabase.__new__(TrainingDatabase)
    db.dsn = _TEST_DSN
    db._pool = _FakePool(_FakeConn(cursor))
    return db


def test_record_llm_call_inserts_and_returns_id():
    log = []
    cur = _FakeCursor(log, fetchone_val=(4242,))
    db = _make_db(cur)

    row_id = db.record_llm_call(
        call_type="controls",
        symbol="BTC-USDT",
        profile="aggressive",
        prompt="LIMITS={...}\nCONTEXT={...}",
        response_text='{"min_confidence":0.6}',
        response_json={"min_confidence": 0.6},
        model="trading-analyst",
        host="http://192.168.15.2:11544",
        latency_ms=812.5,
        trigger="periodic",
        metadata={"regime": "BULLISH"},
    )

    assert row_id == 4242
    assert len(log) == 1
    sql, params = log[0]
    assert "INSERT INTO btc.llm_calls" in sql
    # call_type, symbol, profile e prompt vão como parâmetros (índices 1,2,3,7)
    assert params[1] == "controls"
    assert params[2] == "BTC-USDT"
    assert params[3] == "aggressive"
    assert params[7] == "LIMITS={...}\nCONTEXT={...}"
    assert params[8] == '{"min_confidence":0.6}'
    # response_json e metadata devem estar serializados como JSON string
    assert json.loads(params[9]) == {"min_confidence": 0.6}
    assert json.loads(params[11]) == {"regime": "BULLISH"}


def test_record_llm_call_handles_null_optionals():
    log = []
    cur = _FakeCursor(log, fetchone_val=(1,))
    db = _make_db(cur)

    db.record_llm_call(
        call_type="plan",
        symbol="ETH-USDT",
        profile="conservative",
        prompt="Você é um analista...",
    )

    _, params = log[0]
    # response_text, response_json, latency_ms, metadata → None quando ausentes
    assert params[8] is None   # response_text
    assert params[9] is None   # response_json
    assert params[10] is None  # latency_ms
    assert params[11] is None  # metadata


def test_get_llm_calls_builds_filtered_query():
    log = []
    rows = [{"id": 1, "call_type": "window", "prompt": "p"}]
    cur = _FakeCursor(log, fetchall_val=rows)
    db = _make_db(cur)

    out = db.get_llm_calls(
        call_type="window", symbol="BTC-USDT", profile="aggressive",
        since=1000.0, limit=50,
    )

    assert out == rows
    sql, params = log[0]
    assert "SELECT * FROM btc.llm_calls" in sql
    assert "call_type = %s" in sql
    assert "symbol = %s" in sql
    assert "profile = %s" in sql
    assert "timestamp > %s" in sql
    assert "ORDER BY timestamp ASC LIMIT %s" in sql
    assert params == ["window", "BTC-USDT", "aggressive", 1000.0, 50]


def test_get_llm_calls_without_filters():
    log = []
    cur = _FakeCursor(log, fetchall_val=[])
    db = _make_db(cur)

    db.get_llm_calls(limit=10)

    sql, params = log[0]
    assert "WHERE 1=1" in sql
    # só o LIMIT vira parâmetro quando não há filtros
    assert params == [10]


def test_prune_llm_calls_deletes_by_age_and_returns_count():
    log = []
    cur = _FakeCursor(log, rowcount=7)
    db = _make_db(cur)

    removed = db.prune_llm_calls(max_age_days=30)

    assert removed == 7
    sql, params = log[0]
    assert "DELETE FROM btc.llm_calls WHERE timestamp < %s" in sql
    # cutoff deve estar no passado
    import time as _t
    assert params[0] < _t.time()


def test_get_llm_log_config_returns_defaults_when_missing():
    log = []
    cur = _FakeCursor(log, fetchone_val=None)
    db = _make_db(cur)

    cfg = db.get_llm_log_config()

    assert cfg["enabled"] is True
    assert cfg["sample_rate"] == 1.0
    assert cfg["max_prompt_chars"] == 0
    assert cfg["prune_days"] == 90


def test_get_llm_log_config_reads_row():
    log = []
    row = {
        "id": 1, "enabled": False, "log_controls": True, "log_window": False,
        "log_plan": True, "sample_rate": 0.5, "max_prompt_chars": 2048,
        "prune_days": 30, "updated_at": "2026-07-06T12:00:00Z", "updated_by": "panel",
    }
    cur = _FakeCursor(log, fetchone_val=row)
    db = _make_db(cur)

    cfg = db.get_llm_log_config()

    assert cfg["enabled"] is False
    assert cfg["log_window"] is False
    assert cfg["sample_rate"] == 0.5
    assert cfg["max_prompt_chars"] == 2048
    assert cfg["updated_by"] == "panel"


def test_set_llm_log_config_validates_and_clamps():
    log = []
    # get_llm_log_config (chamado no fim) devolve esta linha
    row = {
        "id": 1, "enabled": True, "log_controls": True, "log_window": True,
        "log_plan": True, "sample_rate": 1.0, "max_prompt_chars": 0,
        "prune_days": 90, "updated_at": None, "updated_by": "tester",
    }
    cur = _FakeCursor(log, fetchone_val=row)
    db = _make_db(cur)

    db.set_llm_log_config(
        updated_by="tester", enabled=False, sample_rate=5.0,
        max_prompt_chars=-10, prune_days=0, ignored_key="x",
    )

    # Encontra o UPDATE emitido e checa o clamping.
    update = [(sql, params) for sql, params in log if sql.startswith("UPDATE btc.llm_log_config")]
    assert update, "esperado um UPDATE"
    sql, params = update[0]
    assert "enabled = %s" in sql
    assert "sample_rate = %s" in sql
    # sample_rate clampado para 1.0, max_prompt_chars→0, prune_days→1 (mín)
    assert 1.0 in params
    assert 0 in params
    assert 1 in params
    assert "ignored_key" not in sql


def test_set_llm_log_config_noop_returns_current():
    log = []
    row = {"id": 1, "enabled": True, "log_controls": True, "log_window": True,
           "log_plan": True, "sample_rate": 1.0, "max_prompt_chars": 0,
           "prune_days": 90, "updated_at": None, "updated_by": None}
    cur = _FakeCursor(log, fetchone_val=row)
    db = _make_db(cur)

    db.set_llm_log_config(updated_by="x")  # nenhum campo válido

    # Sem UPDATE: apenas o SELECT do get_llm_log_config.
    assert not any(sql.startswith("UPDATE") for sql, _ in log)


def test_get_llm_call_stats_aggregates():
    log = []
    by_type_rows = [
        {"call_type": "controls", "total": 10, "last_24h": 4},
        {"call_type": "plan", "total": 3, "last_24h": 1},
    ]
    cur = _FakeCursor(log, fetchone_val={"n": 13, "last_ts": 1783379000.0},
                      fetchall_val=by_type_rows)
    db = _make_db(cur)

    stats = db.get_llm_call_stats()

    assert stats["total"] == 13
    assert stats["by_type"]["controls"] == {"total": 10, "last_24h": 4}
    assert stats["last_ts"] == 1783379000.0


def test_agent_record_llm_call_is_non_blocking():
    """Uma falha do DB não pode propagar para o caminho de decisão.

    Reproduz o corpo real de TradingAgent._record_llm_call sobre um self falso,
    sem importar a classe inteira (pesada). O contrato testado é o try/except.
    """
    import logging

    class _RaisingDB:
        def record_llm_call(self, **kwargs):
            raise RuntimeError("db down")

    logger = logging.getLogger("test-llm")

    class _FakeAgent:
        symbol = "BTC-USDT"
        db = _RaisingDB()

        def _current_profile(self):
            return "aggressive"

        def _record_llm_call(self, *, call_type, prompt, response_text=None,
                             response_json=None, model=None, host=None,
                             latency_ms=None, trigger=None, metadata=None):
            try:
                self.db.record_llm_call(
                    call_type=call_type, symbol=self.symbol,
                    profile=self._current_profile(), prompt=prompt,
                    response_text=response_text, response_json=response_json,
                    model=model, host=host, latency_ms=latency_ms,
                    trigger=trigger, metadata=metadata,
                )
            except Exception as e:
                logger.debug(f"llm_call log skipped ({call_type}): {e}")

    # Não deve levantar exceção mesmo com o DB falhando.
    _FakeAgent()._record_llm_call(call_type="controls", prompt="p")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
