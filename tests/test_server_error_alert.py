from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import server_error_alert as sea


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_glpi_api_url_accepts_public_index_entrypoint() -> None:
    assert sea._glpi_api_url("initSession", "https://auth.rpa4all.com/cmdb/glpi/index.php") == (
        "https://auth.rpa4all.com/cmdb/glpi/apirest.php/initSession"
    )


def test_glpi_ticket_url_strips_apirest_suffix() -> None:
    assert sea._glpi_ticket_url(42, "http://localhost:18092/apirest.php") == (
        "http://localhost:18092/front/ticket.form.php?id=42"
    )


def test_wikijs_raw_url_avoids_duplicate_suffix() -> None:
    assert sea._wikijs_raw_url("http://127.0.0.1:8503/wiki/raw") == (
        "http://127.0.0.1:8503/wiki/raw"
    )


def test_build_wikijs_public_url_includes_locale_prefix() -> None:
    assert sea._build_wikijs_public_url(
        "incidentes/node-exporter-123",
        locale="pt",
        base_url="https://wiki.rpa4all.com",
    ) == "https://wiki.rpa4all.com/pt/incidentes/node-exporter-123"


def test_create_wikijs_page_sends_explicit_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _FakeResponse({"ok": True, "page_id": 10, "wiki_path": "incidentes/node-exporter"})

    monkeypatch.setattr(sea, "WIKIJS_LOCALE", "pt")
    monkeypatch.setattr(sea.urllib.request, "urlopen", fake_urlopen)

    assert sea.create_wikijs_page("Incidente", "# Conteudo", "incidentes/node-exporter") is True
    assert captured["url"] == "http://127.0.0.1:8503/wiki/raw"
    assert captured["body"]["locale"] == "pt"
    assert captured["body"]["wiki_path"] == "incidentes/node-exporter"
