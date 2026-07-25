"""Regressão do deadlock de migração de schema dos crypto-agent.

Incidente 2026-07-25 (deploy run 30177183701): dois agentes que subiram com 1s
de diferença morreram com `psycopg2.errors.DeadlockDetected` em
`_ensure_schema()`. 5 ocorrências em 24h, 12 das 14 instâncias atingidas.

Causa: `PROFILE_MIGRATION_SQL` rodava a cada start, com 13 `ALTER TABLE`
(AccessExclusiveLock em btc.trades/decisions/ai_plans) e `UPDATE` de tabela
inteira — enquanto os outros 13 agentes negociavam nessas mesmas tabelas.
O `pg_advisory_xact_lock` serializa agentes entre si, mas não protege contra
as transações de quem já está rodando: o par DDL×DML fecha o ciclo.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = (REPO_ROOT / "btc_trading_agent" / "training_db.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Paridade entre o SQL e a lista usada para pular a migração
# --------------------------------------------------------------------------

def _migration_sql() -> str:
    start = SOURCE.index('PROFILE_MIGRATION_SQL = f"""')
    return SOURCE[start:SOURCE.index('"""', start + 30)]


def _declared_columns() -> set[tuple[str, str, str]]:
    body = re.search(r"PROFILE_MIGRATION_COLUMNS = \((.*?)\n\)", SOURCE, re.S).group(1)
    return set(ast.literal_eval("[" + body.strip().rstrip(",") + "]"))


def test_declared_columns_match_the_migration_sql() -> None:
    """Se alguém adicionar um ALTER TABLE sem atualizar a lista, o skip passaria
    a pular uma migração ainda necessária — silenciosamente."""
    in_sql = {
        (table, column)
        for table, column in re.findall(
            r"ALTER TABLE \{SCHEMA\}\.(\w+)\s+ADD COLUMN IF NOT EXISTS (\w+)",
            _migration_sql(),
        )
    }
    declared = {(table, column) for table, column, _ in _declared_columns()}
    assert declared == in_sql, (
        "PROFILE_MIGRATION_COLUMNS fora de paridade com PROFILE_MIGRATION_SQL. "
        f"Só no SQL: {in_sql - declared} | só na lista: {declared - in_sql}"
    )


def test_declared_defaults_match_the_migration_sql() -> None:
    sql = _migration_sql()
    for table, column, default in _declared_columns():
        assert re.search(
            rf"ALTER TABLE \{{SCHEMA\}}\.{table}\s+ALTER COLUMN {column} SET DEFAULT '{default}'",
            sql,
        ), f"{table}.{column} declarado com default '{default}', ausente no SQL"


# --------------------------------------------------------------------------
# Comportamento de _profile_migration_applied / _ensure_schema
# --------------------------------------------------------------------------

# psycopg2 e numpy sao reais no ambiente de teste; so o secrets_helper precisa
# de DATABASE_URL para nao tentar falar com o Secrets Agent no import.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
sys.path.insert(0, str(REPO_ROOT / "btc_trading_agent"))

import training_db as db_module  # noqa: E402


class FakeCursor:
    """Cursor que devolve o estado de information_schema.columns."""

    def __init__(self, rows):
        self._rows = rows
        self.executed: list[str] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchall(self):
        return self._rows


def _rows_from(columns, *, nullable="NO", default_suffix="::text"):
    return [
        (table, column, nullable, f"'{default}'{default_suffix}")
        for table, column, default in columns
    ]


def test_skips_migration_when_already_applied() -> None:
    db = db_module.TrainingDatabase
    cur = FakeCursor(_rows_from(db_module.PROFILE_MIGRATION_COLUMNS))
    assert db._profile_migration_applied(cur) is True


def test_runs_migration_when_a_column_is_missing() -> None:
    db = db_module.TrainingDatabase
    partial = list(db_module.PROFILE_MIGRATION_COLUMNS)[:-1]
    cur = FakeCursor(_rows_from(partial))
    assert db._profile_migration_applied(cur) is False


def test_runs_migration_when_column_still_nullable() -> None:
    """Schema meio migrado (coluna criada, SET NOT NULL não aplicado)."""
    db = db_module.TrainingDatabase
    cur = FakeCursor(_rows_from(db_module.PROFILE_MIGRATION_COLUMNS, nullable="YES"))
    assert db._profile_migration_applied(cur) is False


def test_runs_migration_when_default_is_missing() -> None:
    db = db_module.TrainingDatabase
    rows = [
        (table, column, "NO", None)
        for table, column, _ in db_module.PROFILE_MIGRATION_COLUMNS
    ]
    assert db._profile_migration_applied(FakeCursor(rows)) is False


def test_runs_migration_when_default_differs() -> None:
    """Default presente mas com outro valor — não pode contar como aplicado."""
    db = db_module.TrainingDatabase
    rows = [
        (table, column, "NO", "'outro'::text")
        for table, column, _ in db_module.PROFILE_MIGRATION_COLUMNS
    ]
    assert db._profile_migration_applied(FakeCursor(rows)) is False


# --------------------------------------------------------------------------
# Retry
# --------------------------------------------------------------------------

def test_ensure_schema_retries_on_deadlock(monkeypatch) -> None:
    db = db_module.TrainingDatabase.__new__(db_module.TrainingDatabase)
    monkeypatch.setattr(db_module.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise db_module.psycopg2.errors.DeadlockDetected("deadlock detected")

    monkeypatch.setattr(db, "_ensure_schema_once", flaky)
    db._ensure_schema()
    assert calls["n"] == 3


def test_ensure_schema_reraises_after_max_attempts(monkeypatch) -> None:
    db = db_module.TrainingDatabase.__new__(db_module.TrainingDatabase)
    monkeypatch.setattr(db_module.time, "sleep", lambda _s: None)

    def always_deadlock():
        raise db_module.psycopg2.errors.DeadlockDetected("deadlock detected")

    monkeypatch.setattr(db, "_ensure_schema_once", always_deadlock)
    with pytest.raises(db_module.psycopg2.errors.DeadlockDetected):
        db._ensure_schema()


def test_ensure_schema_does_not_retry_other_errors(monkeypatch) -> None:
    """Erro de programação tem que aparecer na hora, não virar 5 tentativas."""
    db = db_module.TrainingDatabase.__new__(db_module.TrainingDatabase)
    monkeypatch.setattr(db_module.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("erro de programação")

    monkeypatch.setattr(db, "_ensure_schema_once", boom)
    with pytest.raises(ValueError):
        db._ensure_schema()
    assert calls["n"] == 1


def test_migration_runs_under_lock_timeout() -> None:
    """Sem lock_timeout o ALTER TABLE fica na fila atrás dos agentes ativos."""
    assert "SET LOCAL lock_timeout" in SOURCE
    assert "pg_advisory_xact_lock" in SOURCE
    # o timeout precisa ser aplicado ANTES do DDL
    assert SOURCE.index("SET LOCAL lock_timeout") < SOURCE.index("cur.execute(PROFILE_MIGRATION_SQL)")
