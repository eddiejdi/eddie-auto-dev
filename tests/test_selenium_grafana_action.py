#!/usr/bin/env python3
"""Testes unitários para o saneamento de URLs do Grafana."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "selenium_grafana_action.py"
_SPEC = importlib.util.spec_from_file_location("selenium_grafana_action", str(_TOOL_PATH))
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["selenium_grafana_action"] = _MODULE
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)


def test_extract_view_panel_dom_id_from_numeric_value() -> None:
    url = "https://grafana.example/d/x/y?viewPanel=89"
    assert _MODULE._extract_view_panel_dom_id(url) == "panel-89"


def test_extract_view_panel_dom_id_from_panel_prefixed_value() -> None:
    url = "https://grafana.example/d/x/y?viewPanel=panel-89"
    assert _MODULE._extract_view_panel_dom_id(url) == "panel-89"


def test_extract_view_panel_dom_id_strips_trailing_bracket() -> None:
    url = "https://grafana.example/d/x/y?viewPanel=panel-89]"
    assert _MODULE._extract_view_panel_dom_id(url) == "panel-89"


def test_sanitize_grafana_url_canonicalizes_view_panel() -> None:
    raw_url = (
        "https://grafana.example/d/x/y?"
        "orgId=1&var-profile=aggressive&viewPanel=panel-89]"
    )
    expected = (
        "https://grafana.example/d/x/y?"
        "orgId=1&var-profile=aggressive&viewPanel=89"
    )
    assert _MODULE._sanitize_grafana_url(raw_url) == expected


def test_sanitize_grafana_url_preserves_other_urls() -> None:
    url = "https://grafana.example/d/x/y?orgId=1&viewPanel=89&refresh=30s"
    assert _MODULE._sanitize_grafana_url(url) == url
