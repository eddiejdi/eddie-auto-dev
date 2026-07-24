#!/usr/bin/env python3
"""Tests for shared taxonomy metadata helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.taxonomy_meta import (
    detect_status_from_openapi_op,
    detect_status_from_text,
    extract_tables_from_openapi_op,
    parse_taxonomy_annotations,
    resolve_owner_from_path,
    resolve_table_refs,
)


class TestOwnership:
    def test_btc_path(self):
        meta = resolve_owner_from_path("btc_trading_agent/training_db.py", schema="btc")
        assert meta["owner"] == "btc_trading_agent"
        assert meta["team"] == "trading"

    def test_schema_fallback(self):
        meta = resolve_owner_from_path("unknown/place.sql", schema="marketing")
        assert meta["owner"] == "marketing"


class TestAnnotations:
    def test_taxonomy_block(self):
        blob = "# taxonomy: tables=btc.trades,clear.trades; status=deprecated; owner=mt5_bridge\n"
        ann = parse_taxonomy_annotations(blob)
        assert ann["status"] == "deprecated"
        assert ann["owner"] == "mt5_bridge"
        assert "btc.trades" in ann["tables"]
        assert "clear.trades" in ann["tables"]

    def test_tables_shorthand(self):
        blob = "# tables: marketing.leads\n@app.get('/leads')\n"
        ann = parse_taxonomy_annotations(blob)
        assert ann["tables"] == ["marketing.leads"]

    def test_deprecated_marker(self):
        assert detect_status_from_text("@deprecated\ndef foo(): pass") == "deprecated"


class TestOpenAPI:
    def test_x_tables_and_deprecated(self):
        op = {
            "summary": "List models",
            "deprecated": True,
            "x-tables": ["btc.llm_calls", "btc.llm_log_config"],
        }
        assert detect_status_from_openapi_op(op) == "deprecated"
        tables = extract_tables_from_openapi_op(op)
        assert "btc.llm_calls" in tables
        assert "btc.llm_log_config" in tables


class TestResolveRefs:
    def test_unambiguous_bare_name(self):
        known = {"btc.trades", "clear.decisions"}
        assert resolve_table_refs(["trades"], known) == ["btc.trades"]
