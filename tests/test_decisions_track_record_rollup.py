#!/usr/bin/env python3
"""Testes unitários para scripts/decisions_track_record_rollup.py.

Cobre: ensure_table, refresh, main, parsing de argumentos e tratamento
de erros. Todas as dependências externas (DB) são mockadas.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Garantir que scripts/ está no sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from decisions_track_record_rollup import SCHEMA, ensure_table, main, refresh


@pytest.fixture
def mock_conn():
    """Conexão PostgreSQL mockada com cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 7
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestEnsureTable:
    def test_creates_rollup_table_with_correct_schema(self, mock_conn: tuple) -> None:
        conn, cursor = mock_conn
        ensure_table(conn)

        assert cursor.execute.call_count == 2
        create_sql = cursor.execute.call_args_list[0][0][0]
        assert "CREATE TABLE IF NOT EXISTS" in create_sql
        assert f"{SCHEMA}.decisions_track_record_hourly" in create_sql
        assert "symbol TEXT NOT NULL" in create_sql
        assert "profile TEXT NOT NULL" in create_sql
        assert "servidor TEXT NOT NULL" in create_sql
        assert "bucket_hour TIMESTAMPTZ NOT NULL" in create_sql
        assert "PRIMARY KEY (symbol, profile, servidor, bucket_hour)" in create_sql

    def test_creates_bucket_index(self, mock_conn: tuple) -> None:
        conn, cursor = mock_conn
        ensure_table(conn)

        index_sql = cursor.execute.call_args_list[1][0][0]
        assert "CREATE INDEX IF NOT EXISTS" in index_sql
        assert "bucket_hour" in index_sql


class TestRefresh:
    def test_upserts_with_since_param(self, mock_conn: tuple) -> None:
        conn, cursor = mock_conn
        since = datetime.now(timezone.utc) - timedelta(hours=3)

        rows = refresh(conn, since)

        assert rows == 7
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "ON CONFLICT (symbol, profile, servidor, bucket_hour) DO UPDATE" in sql
        assert "track_record_trs" in sql
        assert "track_record_boost" in sql
        assert params["since_epoch"] == pytest.approx(since.timestamp())

    def test_filters_by_timestamp_and_profile(self, mock_conn: tuple) -> None:
        conn, cursor = mock_conn
        since = datetime.now(timezone.utc)

        refresh(conn, since)

        sql = cursor.execute.call_args[0][0]
        assert '"timestamp" >= %(since_epoch)s' in sql
        assert "profile IS NOT NULL" in sql


class TestMain:
    @patch("decisions_track_record_rollup.psycopg2.connect")
    @patch("decisions_track_record_rollup.refresh", return_value=42)
    @patch("decisions_track_record_rollup.ensure_table")
    @patch("decisions_track_record_rollup.DATABASE_URL", "postgresql://u:p@host/db")
    def test_main_default_args(
        self,
        mock_ensure: MagicMock,
        mock_refresh: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch("sys.argv", ["decisions_track_record_rollup.py"]):
            result = main()

        assert result == 0
        mock_ensure.assert_called_once()
        mock_refresh.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("decisions_track_record_rollup.psycopg2.connect")
    @patch("decisions_track_record_rollup.refresh", return_value=1)
    @patch("decisions_track_record_rollup.ensure_table")
    @patch("decisions_track_record_rollup.DATABASE_URL", "postgresql://u:p@host/db")
    def test_main_backfill_overrides_hours_back(
        self,
        mock_ensure: MagicMock,
        mock_refresh: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        mock_connect.return_value = MagicMock()

        with patch(
            "sys.argv",
            ["decisions_track_record_rollup.py", "--backfill", "2160", "--hours-back", "3"],
        ):
            main()

        since_arg = mock_refresh.call_args[0][1]
        expected = datetime.now(timezone.utc) - timedelta(hours=2160)
        assert abs((since_arg - expected).total_seconds()) < 5

    @patch("decisions_track_record_rollup.DATABASE_URL", None)
    def test_main_missing_database_url(self) -> None:
        with patch("sys.argv", ["decisions_track_record_rollup.py"]):
            result = main()

        assert result == 1

    @patch("decisions_track_record_rollup.psycopg2.connect")
    @patch("decisions_track_record_rollup.DATABASE_URL", "postgresql://u:p@host/db")
    def test_main_db_connection_failure(self, mock_connect: MagicMock) -> None:
        mock_connect.side_effect = Exception("Connection refused")

        with patch("sys.argv", ["decisions_track_record_rollup.py"]):
            result = main()

        assert result == 1

    @patch("decisions_track_record_rollup.psycopg2.connect")
    @patch("decisions_track_record_rollup.refresh", side_effect=Exception("boom"))
    @patch("decisions_track_record_rollup.ensure_table")
    @patch("decisions_track_record_rollup.DATABASE_URL", "postgresql://u:p@host/db")
    def test_main_rolls_back_on_refresh_failure(
        self,
        mock_ensure: MagicMock,
        mock_refresh: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch("sys.argv", ["decisions_track_record_rollup.py"]):
            result = main()

        assert result == 1
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
