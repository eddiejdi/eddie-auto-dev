#!/usr/bin/env python3
"""Testes do backend do painel de log de LLM (scripts/llm_log_panel_server.py).

Sobe o servidor HTTP numa porta efêmera com um DB falso e exercita as rotas:
static (HTML/JS), GET/POST /api/config e o gate de API key.
"""

from pathlib import Path
import json
import os
import sys
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

# DSN sem credenciais — o servidor usa um DB falso; nenhuma conexão real.
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")

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


@pytest.fixture
def server(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(panel, "_DB", fake)
    monkeypatch.setattr(panel, "API_KEY", "")
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
    assert b"Log de chamadas ao LLM" in body


def test_serves_js(server):
    base, _ = server
    status, body, ctype = _get(base + "/llm_log_panel.js")
    assert status == 200
    assert "javascript" in ctype
    assert b"/api/config" in body


def test_get_config_returns_config_and_stats(server):
    base, _ = server
    status, body, _ = _get(base + "/api/config")
    data = json.loads(body)
    assert status == 200
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
    # sem header → 401
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base + "/api/config")
    assert exc.value.code == 401
    # com header correto → 200
    status, _, _ = _get(base + "/api/config", key="s3cr3t")
    assert status == 200


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
