#!/usr/bin/env python3
"""Tests for table taxonomy gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hooks import table_registry_validate as trv

CATALOG = {
    "btc.trades": "trading",
    "trades": "trading",
    "public.agent_actions": "governance",
    "agent_actions": "governance",
}


class TestExtract:
    def test_create_table_with_schema(self):
        blob = "CREATE TABLE IF NOT EXISTS clear.decisions (id INT);"
        found = trv.extract_candidates(blob)
        assert "clear.decisions" in found

    def test_schema_const(self):
        blob = 'SCHEMA = "btc"\nCREATE TABLE IF NOT EXISTS {SCHEMA}.candles (id INT);'
        found = trv.extract_candidates(blob)
        assert "btc.candles" in found


class TestClassify:
    def test_exact_ok(self):
        status, _ = trv.classify("btc.trades", CATALOG)
        assert status == "ok"

    def test_fuzzy_duplicate(self):
        status, msg = trv.classify("btc.tradez", CATALOG)
        assert status == "duplicate"
        assert "btc.trades" in msg

    def test_new_table(self):
        status, _ = trv.classify("public.completely_new_table_xyz", CATALOG)
        assert status == "new"


class TestSkipAndReserved:
    def test_skips_docs_prefix(self):
        assert trv._should_skip_path("docs/taxonomy/TABLES.md")
        assert trv._should_skip_path("tests/test_catalog_tables.py")
        assert trv._should_skip_path("tools/catalog_tables.py")
        assert not trv._should_skip_path("marketing/db_migrate.py")

    def test_reserved_words_not_candidates(self):
        # incomplete / prose fragments must not become table names
        blob = "CREATE TABLE IF NOT EXISTS something_real (id INT);\nCREATE TABLE IF\nfor example"
        found = trv.extract_candidates(blob)
        assert "something_real" in found or "public.something_real" in found
        assert "if" not in found
        assert "public.if" not in found
        assert "for" not in found
