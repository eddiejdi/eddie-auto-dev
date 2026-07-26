#!/usr/bin/env python3
"""Tests for taxonomy lifecycle inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.catalog_taxonomy_lifecycle import (
    annotate_api_orphan_flags,
    apply_unused_to_tables,
    entities_with_strong_links,
    run_lifecycle,
)


def test_entities_with_strong_links():
    graph = {
        "edges": [
            {
                "from": {"type": "api", "id": "GET /x"},
                "to": {"type": "table", "id": "btc.trades"},
                "relation": "explicit",
                "weight": 1.0,
            },
            {
                "from": {"type": "table", "id": "btc.orphan"},
                "to": {"type": "domain", "id": "trading"},
                "relation": "in_domain",
                "weight": 0.5,
            },
        ]
    }
    tables, apis = entities_with_strong_links(graph)
    assert "btc.trades" in tables
    assert "GET /x" in apis
    assert "btc.orphan" not in tables


def test_apply_unused_and_restore(tmp_path: Path):
    cat = {
        "categories": {
            "trading": {
                "btc.trades": {"name": "trades", "status": "active"},
                "btc.orphan": {"name": "orphan", "status": "active"},
            }
        },
        "metadata": {},
    }
    cat, newly = apply_unused_to_tables(cat, {"btc.trades"})
    assert cat["categories"]["trading"]["btc.orphan"]["status"] == "unused"
    assert "btc.orphan" in newly
    assert cat["categories"]["trading"]["btc.trades"]["status"] == "active"

    # restore when linked again
    cat["categories"]["trading"]["btc.orphan"]["status"] = "unused"
    cat, _ = apply_unused_to_tables(cat, {"btc.trades", "btc.orphan"})
    assert cat["categories"]["trading"]["btc.orphan"]["status"] == "active"


def test_orphan_apis_skip_health():
    cat = {
        "categories": {
            "health": {
                "GET /health": {"path": "/health", "category": "health", "relatedTables": []},
            },
            "trading": {
                "POST /order": {
                    "path": "/order",
                    "category": "trading",
                    "relatedTables": ["btc.trades"],
                },
                "GET /lonely": {"path": "/lonely", "category": "trading", "relatedTables": []},
            },
        },
        "metadata": {},
    }
    cat, orphans = annotate_api_orphan_flags(cat, {"POST /order"})
    assert "GET /health" not in orphans
    assert "POST /order" not in orphans
    assert "GET /lonely" in orphans
    assert cat["categories"]["trading"]["GET /lonely"]["orphan"] is True


def test_run_lifecycle_end_to_end(tmp_path: Path):
    (tmp_path / ".taxonomy-catalog").mkdir()
    (tmp_path / ".tables-catalog").mkdir()
    (tmp_path / ".apis-catalog").mkdir()
    (tmp_path / "docs" / "taxonomy").mkdir(parents=True)

    tables = {
        "categories": {
            "trading": {
                "btc.trades": {"name": "trades", "owner": "btc_trading_agent", "team": "trading"},
                "btc.ghost": {"name": "ghost", "owner": "unknown", "team": "unassigned"},
            }
        },
        "metadata": {},
    }
    apis = {
        "categories": {
            "trading": {
                "POST /order": {
                    "path": "/order",
                    "service": "mt5_bridge",
                    "owner": "mt5_bridge",
                    "team": "trading",
                    "relatedTables": ["btc.trades"],
                }
            }
        },
        "metadata": {},
    }
    graph = {
        "domains": {"trading": {"variables": 1, "tables": 2, "apis": 1}},
        "edges": [
            {
                "from": {"type": "api", "id": "POST /order"},
                "to": {"type": "table", "id": "btc.trades"},
                "relation": "explicit",
                "weight": 1.0,
            }
        ],
    }
    (tmp_path / ".tables-catalog" / "catalog.json").write_text(json.dumps(tables))
    (tmp_path / ".apis-catalog" / "catalog.json").write_text(json.dumps(apis))
    (tmp_path / ".taxonomy-catalog" / "graph.json").write_text(json.dumps(graph))

    summary = run_lifecycle(tmp_path)
    assert summary["unusedTables"] >= 1
    assert (tmp_path / ".taxonomy-catalog" / "ORPHANS.md").exists()
    assert (tmp_path / ".taxonomy-catalog" / "OWNERSHIP_GAPS.md").exists()
    assert (tmp_path / ".taxonomy-catalog" / "DOMAIN_MAP.md").exists()

    updated = json.loads((tmp_path / ".tables-catalog" / "catalog.json").read_text())
    assert updated["categories"]["trading"]["btc.ghost"]["status"] == "unused"
    assert updated["categories"]["trading"]["btc.trades"]["status"] == "active"
