#!/usr/bin/env python3
"""Regressões para TrainingDatabase.update_trade_fill.

Corrige size/price de um trade com o fill real da exchange. Só deve alcançar
trades live e não fechados: um trade fechado teve o PnL calculado sobre o size
antigo, e reescrevê-lo sem recalcular o PnL deixaria os dois inconsistentes.
"""

from pathlib import Path
import os
import sys
import types

import unittest.mock as _mock

import pytest


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

_psycopg2_mock = types.ModuleType("psycopg2")
_psycopg2_mock.extras = types.SimpleNamespace(RealDictCursor=object)
_psycopg2_mock.pool = types.SimpleNamespace(
    ThreadedConnectionPool=object,
    SimpleConnectionPool=object,
)
_psycopg2_mock.Error = Exception
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", _psycopg2_mock.extras)
sys.modules.setdefault("psycopg2.pool", _psycopg2_mock.pool)

_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)

import training_db as tdb_mod
from training_db import TrainingDatabase


REAL_SIZE = 0.00023643
REAL_PRICE = 63_443.5


def _db(rowcount=1):
    """TrainingDatabase com _get_conn stubado, expondo o cursor para asserts."""
    db = TrainingDatabase.__new__(TrainingDatabase)

    cur = _mock.MagicMock()
    cur.rowcount = rowcount
    conn = _mock.MagicMock()
    conn.__enter__ = _mock.MagicMock(return_value=conn)
    conn.__exit__ = _mock.MagicMock(return_value=False)
    conn.cursor.return_value = cur

    db._get_conn = _mock.MagicMock(return_value=conn)
    return db, cur


def _sql(cur) -> str:
    return " ".join(cur.execute.call_args[0][0].split())


def test_updates_size_and_price() -> None:
    db, cur = _db()

    assert db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE) is True

    sql = _sql(cur)
    assert "SET size = %s, price = %s" in sql
    params = cur.execute.call_args[0][1]
    assert params == (REAL_SIZE, REAL_PRICE, 3833)


def test_includes_funds_when_provided() -> None:
    db, cur = _db()

    db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE, funds=15.0)

    assert "funds = %s" in _sql(cur)
    assert cur.execute.call_args[0][1] == (REAL_SIZE, REAL_PRICE, 15.0, 3833)


def test_omits_funds_when_absent_or_zero() -> None:
    for funds in (None, 0, 0.0):
        db, cur = _db()
        db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE, funds=funds)
        assert "funds" not in _sql(cur)


def test_guards_scope_to_live_and_open_trades() -> None:
    """Nunca reescreve dry_run nem trade fechado (PnL já calculado)."""
    db, cur = _db()

    db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE)

    sql = _sql(cur)
    assert "dry_run = FALSE" in sql
    assert "status != 'closed'" in sql


def test_returns_false_when_no_row_matched() -> None:
    """rowcount=0 → trade fechado/dry_run/inexistente."""
    db, cur = _db(rowcount=0)

    assert db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE) is False


@pytest.mark.parametrize(
    "size,price",
    [(0, REAL_PRICE), (-1, REAL_PRICE), (REAL_SIZE, 0), (REAL_SIZE, -1)],
)
def test_rejects_non_positive_values_without_touching_db(size, price) -> None:
    db, _cur = _db()

    assert db.update_trade_fill(3833, size, price) is False
    db._get_conn.assert_not_called()


def test_targets_trades_table_in_schema() -> None:
    db, cur = _db()

    db.update_trade_fill(3833, REAL_SIZE, REAL_PRICE)

    assert f"UPDATE {tdb_mod.SCHEMA}.trades" in _sql(cur)
