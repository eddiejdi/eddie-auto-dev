#!/usr/bin/env python3
"""Unit tests for Tables Catalog Scanner."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.catalog_tables import TablesCatalog


@pytest.fixture
def temp_workspace(tmp_path: Path):
    (tmp_path / "sql").mkdir()
    return tmp_path


@pytest.fixture
def catalog(temp_workspace: Path):
    return TablesCatalog(root_path=str(temp_workspace))


class TestTablesCatalog:
    def test_scan_sql_create_table(self, catalog: TablesCatalog, temp_workspace: Path):
        sql = temp_workspace / "sql" / "schema.sql"
        sql.write_text(
            """
CREATE SCHEMA IF NOT EXISTS clear;
SET search_path TO clear, public;

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
"""
        )
        catalog.scan_sql_files()
        assert "clear.trades" in catalog.tables
        cols = {c["name"] for c in catalog.tables["clear.trades"]["columns"]}
        assert "id" in cols
        assert "symbol" in cols
        assert catalog.tables["clear.trades"]["indexes"]

    def test_python_schema_const(self, catalog: TablesCatalog, temp_workspace: Path):
        py = temp_workspace / "training_db.py"
        py.write_text(
            """
SCHEMA = "btc"

DDL = f'''
CREATE TABLE IF NOT EXISTS {SCHEMA}.candles (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    open NUMERIC
);
'''
"""
        )
        catalog.scan_python_ddl()
        assert "btc.candles" in catalog.tables
        assert catalog.tables["btc.candles"]["category"] == "trading"

    def test_categorize_governance(self, catalog: TablesCatalog, temp_workspace: Path):
        sql = temp_workspace / "mig.sql"
        sql.write_text(
            """
CREATE TABLE IF NOT EXISTS agent_actions (
    id SERIAL PRIMARY KEY,
    intent_id TEXT UNIQUE NOT NULL
);
"""
        )
        catalog.scan_sql_files()
        assert "public.agent_actions" in catalog.tables
        assert catalog.tables["public.agent_actions"]["category"] == "governance"

    def test_generate_and_save(self, catalog: TablesCatalog, temp_workspace: Path):
        sql = temp_workspace / "t.sql"
        sql.write_text("CREATE TABLE IF NOT EXISTS foo (id INT PRIMARY KEY);")
        data = catalog.generate_catalog()
        assert data["metadata"]["totalTables"] >= 1
        out = catalog.save_catalog()
        assert out.exists()
        catalog.generate_reports(temp_workspace / ".tables-catalog")
        assert (temp_workspace / ".tables-catalog" / "CATALOG_REPORT.md").exists()

    def test_sensitive_column_flag(self, catalog: TablesCatalog, temp_workspace: Path):
        sql = temp_workspace / "users.sql"
        sql.write_text(
            """
CREATE TABLE IF NOT EXISTS portal_users (
    id SERIAL PRIMARY KEY,
    email TEXT,
    password_hash TEXT NOT NULL,
    api_token TEXT
);
"""
        )
        catalog.scan_sql_files()
        t = catalog.tables["public.portal_users"]
        assert t["sensitive"] is True
        assert "password_hash" in t["sensitiveColumns"]
        assert "api_token" in t["sensitiveColumns"]

    def test_owner_and_status_annotation(self, catalog: TablesCatalog, temp_workspace: Path):
        d = temp_workspace / "marketing"
        d.mkdir()
        sql = d / "schema.sql"
        sql.write_text(
            """
-- taxonomy: owner=marketing; status=deprecated
CREATE TABLE IF NOT EXISTS marketing.leads (
    id SERIAL PRIMARY KEY,
    email TEXT
);
"""
        )
        catalog.scan_sql_files()
        t = catalog.tables["marketing.leads"]
        assert t["owner"] == "marketing"
        assert t["status"] == "deprecated"
        assert t["team"] == "growth"
