#!/usr/bin/env python3
"""Testes do backend do painel de auditoria de prompts LLM."""

from pathlib import Path
import json
import os
import sys
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")
os.environ.setdefault("COORDINATOR_URL", "http://127.0.0.1:9")  # unreachable by default

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import llm_log_panel_server as panel  # noqa: E402


class _FakeDB:
    def __init__(self):
        self.cfg = {
            "enabled": True, "log_controls": True, "log_window": True, "log_plan": True,
            "sample_rate": 1.0, "max_prompt_chars": 0, "prune_days": 90,
            "updated_at": None, "updated_by": None,
        }
        self.sets = []
        self.calls = [
            {
                "id": 1,
                "timestamp": 1700000000.0,
                "call_type": "plan",
                "symbol": "BTC",
                "profile": "default",
                "trigger": "test",
                "model": "mistral:7b",
                "host": "http://192.168.15.2:11437",
                "prompt": "PROMPT DE TESTE TRADING completo para auditoria",
                "response_text": "resposta trading",
                "latency_ms": 1200,
            }
        ]

    def get_llm_log_config(self):
        return dict(self.cfg)

    def set_llm_log_config(self, updated_by=None, **fields):
        self.sets.append((updated_by, fields))
        for k in ("enabled", "log_controls", "log_window", "log_plan",
                  "sample_rate", "max_prompt_chars", "prune_days"):
            if k in fields and fields[k] is not None:
                self.cfg[k] = fields[k]
        self.cfg["updated_by"] = updated_by
        return dict(self.cfg)

    def get_llm_call_stats(self):
        return {"by_type": {"controls": {"total": 2, "last_24h": 1}}, "total": 2, "last_ts": None}

    def get_llm_calls(self, **kwargs):
        return list(self.calls)


@pytest.fixture
def server(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(panel, "_DB", fake)
    monkeypatch.setattr(panel, "API_KEY", "")
    monkeypatch.setattr(panel, "DATABASE_URL", "")
    monkeypatch.setattr(panel, "COORDINATOR_URL", "http://127.0.0.1:9")

    def _fake_coord(limit=100):
        return [
            {
                "id": "coord-1",
                "source": "coordinator",
                "ts": "2026-07-26T23:55:09+00:00",
                "model": "gemma3-fast:gpu1",
                "endpoint": "gpu1-gtx1050",
                "path": "/api/generate",
                "status": 200,
                "elapsed_s": 12.4,
                "streaming": False,
                "prompt": "PROMPT COORDINATOR COMPLETO para auditoria da agenda",
                "response": "ok",
                "error": "",
                "prompt_chars": 48,
                "response_chars": 2,
            }
        ]

    monkeypatch.setattr(panel, "_fetch_coordinator_requests", _fake_coord)
    monkeypatch.setattr(panel, "_fetch_pg_payload_log", lambda **kw: [])
    # force _db() to return fake
    monkeypatch.setattr(panel, "_db", lambda: fake)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", fake
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url, key=None):
    req = urllib.request.Request(url)
    if key:
        req.add_header("X-API-KEY", key)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read(), r.headers.get("Content-Type", "")


def _post(url, body, key=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-KEY", key)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


def test_serves_html_index(server):
    base, _ = server
    status, body, ctype = _get(base + "/")
    assert status == 200
    assert "text/html" in ctype
    assert b"Auditoria de Prompts" in body


def test_serves_js(server):
    base, _ = server
    status, body, ctype = _get(base + "/llm_log_panel.js")
    assert status == 200
    assert "javascript" in ctype
    assert b"/api/prompts" in body


def test_get_config_returns_config_and_stats(server):
    base, _ = server
    status, body, _ = _get(base + "/api/config")
    data = json.loads(body)
    assert status == 200
    assert data["available"] is True
    assert data["config"]["enabled"] is True
    assert data["stats"]["total"] == 2


def test_post_config_updates(server):
    base, fake = server
    status, data = _post(base + "/api/config", {"enabled": False, "sample_rate": 0.3})
    assert status == 200
    assert data["config"]["enabled"] is False
    assert data["config"]["sample_rate"] == 0.3
    assert fake.sets and fake.sets[0][1]["enabled"] is False


def test_api_key_required_when_set(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(panel, "API_KEY", "s3cr3t")
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base + "/api/config")
    assert exc.value.code == 401
    status, _, _ = _get(base + "/api/config", key="s3cr3t")
    assert status == 200


def test_api_prompts_returns_all_sources(server):
    base, _ = server
    status, body, _ = _get(base + "/api/prompts?source=all&limit=50")
    data = json.loads(body)
    assert status == 200
    assert data["total"] >= 2
    sources = {i["source"] for i in data["items"]}
    assert "coordinator" in sources
    assert "trading" in sources
    # prompt completo presente (não truncado a 500 no painel)
    coord = next(i for i in data["items"] if i["source"] == "coordinator")
    assert "PROMPT COORDINATOR COMPLETO" in coord["prompt"]


def test_api_prompts_filter_q(server):
    base, _ = server
    status, body, _ = _get(base + "/api/prompts?q=agenda&source=coordinator")
    data = json.loads(body)
    assert status == 200
    assert data["total"] >= 1
    assert all("agenda" in (i["prompt"] + i["response"]).lower() for i in data["items"])


def test_path_prefix_llm_prompts(server):
    base, _ = server
    status, body, ctype = _get(base + "/llm-prompts/")
    assert status == 200
    assert "text/html" in ctype
    status, body, _ = _get(base + "/llm-prompts/api/prompts?source=coordinator")
    data = json.loads(body)
    assert status == 200
    assert data["total"] >= 1


def test_health(server):
    base, _ = server
    status, body, _ = _get(base + "/api/health")
    data = json.loads(body)
    assert status == 200
    assert data["ok"] is True
