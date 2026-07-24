#!/usr/bin/env python3
"""Tests for API taxonomy gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hooks import api_registry_validate as arv

CATALOG = {
    "GET /health": "health",
    "/health": "health",
    "POST /order": "trading",
    "/order": "trading",
    "GET /secrets/{name}": "secrets",
}


class TestExtract:
    def test_fastapi_decorator(self):
        blob = '@app.get("/health")\ndef h():\n    pass\n'
        assert "GET /health" in arv.extract_candidates(blob)

    def test_path_param_normalized(self):
        blob = '@app.get("/secrets/{name:path}")\ndef s():\n    pass\n'
        assert "GET /secrets/{name}" in arv.extract_candidates(blob)


class TestClassify:
    def test_exact_ok(self):
        status, _ = arv.classify("GET /health", CATALOG)
        assert status == "ok"

    def test_new_endpoint(self):
        status, _ = arv.classify("GET /brand-new-endpoint-xyz", CATALOG)
        assert status == "new"

    def test_fuzzy_duplicate_same_method(self):
        status, msg = arv.classify("POST /orderr", CATALOG)
        assert status == "duplicate"
        assert "POST /order" in msg

    def test_short_path_not_fuzzy_against_root(self):
        catalog = {"GET /": "marketing", "GET /health": "health"}
        status, _ = arv.classify("GET /x", catalog)
        assert status == "new"


class TestSkipPaths:
    def test_skips_docs_and_tests(self):
        assert arv._should_skip_path("docs/taxonomy/APIS.md")
        assert arv._should_skip_path("tests/test_catalog_apis.py")
        assert arv._should_skip_path("tools/catalog_apis.py")
        assert not arv._should_skip_path("mt5_bridge/bridge_api.py")
