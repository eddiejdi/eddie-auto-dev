#!/usr/bin/env python3
"""Unit tests for APIs Catalog Scanner."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.catalog_apis import ApisCatalog


@pytest.fixture
def temp_workspace(tmp_path: Path):
    (tmp_path / "svc").mkdir()
    (tmp_path / "docs").mkdir()
    return tmp_path


@pytest.fixture
def catalog(temp_workspace: Path):
    return ApisCatalog(root_path=str(temp_workspace))


class TestApisCatalog:
    def test_fastapi_decorators(self, catalog: ApisCatalog, temp_workspace: Path):
        py = temp_workspace / "svc" / "api.py"
        py.write_text(
            """
from fastapi import FastAPI, APIRouter
app = FastAPI()
router = APIRouter(prefix="/tool-interceptor", tags=["tool-interceptor"])

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/order")
def order():
    pass

@router.get("/stats")
def stats():
    pass
"""
        )
        catalog.scan_python_routes()
        keys = set(catalog.endpoints)
        assert "GET /health" in keys
        assert "POST /order" in keys
        assert "GET /tool-interceptor/stats" in keys

    def test_path_normalization(self, catalog: ApisCatalog):
        assert catalog._normalize_path("/secrets/{name:path}") == "/secrets/{name}"
        assert catalog._normalize_path("orders/") == "/orders"

    def test_openapi_yaml(self, catalog: ApisCatalog, temp_workspace: Path):
        spec = temp_workspace / "docs" / "openapi.yaml"
        spec.write_text(
            """
openapi: 3.0.3
paths:
  /api/v1/models:
    get:
      summary: List models
    post:
      summary: Create model
  /health:
    get:
      summary: Health
"""
        )
        catalog.scan_openapi_specs()
        assert "GET /api/v1/models" in catalog.endpoints
        assert "POST /api/v1/models" in catalog.endpoints
        assert catalog.endpoints["GET /api/v1/models"]["summary"] == "List models"

    def test_categorize_trading(self, catalog: ApisCatalog, temp_workspace: Path):
        py = temp_workspace / "bridge.py"
        py.write_text(
            """
@app.get("/positions")
def positions():
    pass
"""
        )
        catalog.scan_python_routes()
        assert catalog.endpoints["GET /positions"]["category"] == "trading"

    def test_service_hint_reduces_general(self, catalog: ApisCatalog, temp_workspace: Path):
        d = temp_workspace / "tools" / "x_agent"
        d.mkdir(parents=True)
        py = d / "x_agent.py"
        py.write_text(
            """
@app.get("/bookmarks")
def bookmarks():
    pass
"""
        )
        catalog.scan_python_routes()
        assert catalog.endpoints["GET /bookmarks"]["category"] == "social"

    def test_sensitive_flag_on_auth_path(self, catalog: ApisCatalog, temp_workspace: Path):
        py = temp_workspace / "auth.py"
        py.write_text(
            """
@app.post("/login/token")
def login():
    pass
"""
        )
        catalog.scan_python_routes()
        assert catalog.endpoints["POST /login/token"]["sensitive"] is True

    def test_explicit_table_annotation_and_status(self, catalog: ApisCatalog, temp_workspace: Path):
        d = temp_workspace / "mt5_bridge"
        d.mkdir()
        py = d / "bridge_api.py"
        py.write_text(
            """
# taxonomy: tables=btc.trades,clear.trades; status=experimental
@app.post("/order")
def order():
    pass
"""
        )
        catalog.scan_python_routes()
        ep = catalog.endpoints["POST /order"]
        assert ep["status"] == "experimental"
        assert "btc.trades" in ep["relatedTables"]
        assert ep["owner"] == "mt5_bridge"

    def test_openapi_x_tables(self, catalog: ApisCatalog, temp_workspace: Path):
        spec = temp_workspace / "docs" / "openapi.yaml"
        spec.write_text(
            """
openapi: 3.0.3
paths:
  /api/v1/models:
    get:
      summary: List models
      x-tables:
        - btc.llm_calls
      deprecated: true
"""
        )
        catalog.scan_openapi_specs()
        ep = catalog.endpoints["GET /api/v1/models"]
        assert ep["status"] == "deprecated"
        assert "btc.llm_calls" in ep["relatedTables"]


    def test_generate_and_save(self, catalog: ApisCatalog, temp_workspace: Path):
        py = temp_workspace / "a.py"
        py.write_text('@app.get("/x")\ndef x():\n    pass\n')
        data = catalog.generate_catalog()
        assert data["metadata"]["totalEndpoints"] >= 1
        out = catalog.save_catalog()
        assert out.exists()
        catalog.generate_reports(temp_workspace / ".apis-catalog")
        assert (temp_workspace / ".apis-catalog" / "SERVICE_ENDPOINTS.md").exists()
