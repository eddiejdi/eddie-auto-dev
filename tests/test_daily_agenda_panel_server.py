from __future__ import annotations

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_agenda_panel_server as panel  # noqa: E402


@pytest.fixture
def server(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts" / "daily_agenda"
    day = artifacts / "2026-07-09"
    day.mkdir(parents=True)
    (day / "source.txt").write_text("Fonte", encoding="utf-8")
    (day / "locution.txt").write_text("Locucao", encoding="utf-8")
    (day / "locution.wav").write_bytes(b"RIFF")
    monkeypatch.setattr(panel, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(panel, "DEFAULT_JOB_PATH", artifacts / "panel_job.json")
    monkeypatch.setattr(panel, "API_KEY", "")
    monkeypatch.setattr(
        panel,
        "youtube_auth_status",
        lambda _cfg=None: {"authenticated": False, "channel_title": "", "error": ""},
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str):
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as response:
        return response.status, response.read(), response.headers.get("Content-Type", "")


def test_static_and_status(server) -> None:
    base = server
    status, body, ctype = _get(base + "/")
    assert status == 200
    assert "text/html" in ctype
    assert b"Agenda Di" in body

    status, body, ctype = _get(base + "/daily_agenda_panel.js")
    assert status == 200
    assert "javascript" in ctype

    status, body, _ = _get(base + "/api/status")
    payload = json.loads(body.decode())
    assert payload["editions"][0]["date"] == "2026-07-09"
    assert payload["config"]["youtube"]["enabled"] is True


def test_edition_detail_and_audio(server) -> None:
    base = server
    status, body, _ = _get(base + "/api/editions/2026-07-09")
    payload = json.loads(body.decode())
    assert payload["locution"] == "Locucao"
    assert payload["has_wav"] is True

    status, body, ctype = _get(base + "/api/editions/2026-07-09/audio")
    assert status == 200
    assert body == b"RIFF"
    assert ctype == "audio/wav"