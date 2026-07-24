#!/usr/bin/env python3
"""Tests for cross-domain taxonomy graph."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.catalog_taxonomy_graph import build_graph, write_reports


@pytest.fixture
def mini_catalogs(tmp_path: Path):
    (tmp_path / ".variables-catalog").mkdir()
    (tmp_path / ".tables-catalog").mkdir()
    (tmp_path / ".apis-catalog").mkdir()

    vars_cat = {
        "categories": {
            "trading": {
                "EXCHANGE_API_KEY": {"name": "EXCHANGE_API_KEY", "source": ".env"},
                "BTC_ENGINE_API_PORT": {"name": "BTC_ENGINE_API_PORT", "source": "systemd"},
            },
            "database": {
                "DATABASE_URL": {"name": "DATABASE_URL", "source": ".env"},
            },
        }
    }
    tables_cat = {
        "categories": {
            "trading": {
                "btc.trades": {
                    "name": "trades",
                    "schema": "btc",
                    "fqn": "btc.trades",
                    "source": "sql",
                    "locations": [
                        {"file": "btc_trading_agent/training_db.py", "line": 10}
                    ],
                }
            }
        }
    }
    apis_cat = {
        "categories": {
            "trading": {
                "POST /order": {
                    "operationKey": "POST /order",
                    "method": "POST",
                    "path": "/order",
                    "service": "mt5_bridge/bridge_api",
                    "locations": [
                        {"file": "mt5_bridge/bridge_api.py", "line": 1}
                    ],
                },
                "GET /trades": {
                    "operationKey": "GET /trades",
                    "method": "GET",
                    "path": "/trades",
                    "service": "btc_trading_agent/api",
                    "locations": [
                        {"file": "btc_trading_agent/api.py", "line": 1}
                    ],
                },
            }
        }
    }
    (tmp_path / ".variables-catalog" / "catalog.json").write_text(json.dumps(vars_cat))
    (tmp_path / ".tables-catalog" / "catalog.json").write_text(json.dumps(tables_cat))
    (tmp_path / ".apis-catalog" / "catalog.json").write_text(json.dumps(apis_cat))
    return tmp_path


class TestTaxonomyGraph:
    def test_build_graph_has_name_match(self, mini_catalogs: Path):
        graph = build_graph(mini_catalogs)
        assert graph["edgeCount"] > 0
        rels = {e["relation"] for e in graph["edges"]}
        assert "in_domain" in rels
        assert "name_match" in rels  # GET /trades ↔ btc.trades

        name_edges = [
            e
            for e in graph["edges"]
            if e["relation"] == "name_match"
            and e["to"]["id"] == "btc.trades"
        ]
        assert name_edges

    def test_schema_hint_links_btc_db_var(self, mini_catalogs: Path, tmp_path: Path):
        # PORT alone is not configish enough for schema_hint; DB-ish names are.
        vars_path = mini_catalogs / ".variables-catalog" / "catalog.json"
        data = json.loads(vars_path.read_text())
        data["categories"]["trading"]["BTC_DB_HOST"] = {
            "name": "BTC_DB_HOST",
            "source": ".env",
        }
        vars_path.write_text(json.dumps(data))
        graph = build_graph(mini_catalogs)
        schema_edges = [
            e
            for e in graph["edges"]
            if e["relation"] == "schema_hint" and e["to"]["id"] == "btc.trades"
        ]
        assert any(e["from"]["id"] == "BTC_DB_HOST" for e in schema_edges)

    def test_write_reports(self, mini_catalogs: Path):
        graph = build_graph(mini_catalogs)
        out = mini_catalogs / ".taxonomy-catalog"
        write_reports(graph, out)
        assert (out / "graph.json").exists()
        assert (out / "links.csv").exists()
        assert (out / "GRAPH_REPORT.md").exists()

    def test_explicit_related_tables_edge(self, mini_catalogs: Path):
        apis_path = mini_catalogs / ".apis-catalog" / "catalog.json"
        data = json.loads(apis_path.read_text())
        data["categories"]["trading"]["POST /order"]["relatedTables"] = ["btc.trades"]
        apis_path.write_text(json.dumps(data))
        graph = build_graph(mini_catalogs)
        explicit = [
            e
            for e in graph["edges"]
            if e["relation"] == "explicit"
            and e["from"]["id"] == "POST /order"
            and e["to"]["id"] == "btc.trades"
        ]
        assert explicit
        assert explicit[0]["weight"] == 1.0
