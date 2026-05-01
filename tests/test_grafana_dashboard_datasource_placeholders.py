"""Testes para validar UIDs concretos nos dashboards Grafana versionados."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATHS = [
    ROOT / "grafana/dashboards/nas-rpa4all-omv.json",
    ROOT / "grafana/dashboards/squid-proxy.json",
    ROOT / "grafana/dashboards/storj-node-dashboard.json",
    ROOT / "grafana/dashboards/homelab-copilot-agent.json",
]
PLACEHOLDERS = ("${DS_PROMETHEUS}", "${datasource}")
FORBIDDEN_STRINGS = ("\"Loki\"", "\"type\": \"loki\"", "${DS_LOKI}")

@pytest.mark.parametrize("dashboard_path", DASHBOARD_PATHS, ids=lambda path: path.name)
def test_dashboards_nao_contem_uids_placeholder(dashboard_path: Path) -> None:
    """Garante que os dashboards tocados usam UID concreto de datasource."""
    text = dashboard_path.read_text()
    json.loads(text)
    for placeholder in PLACEHOLDERS:
        assert placeholder not in text


@pytest.mark.parametrize("dashboard_path", DASHBOARD_PATHS, ids=lambda path: path.name)
def test_dashboards_nao_contem_dependencias_quebradas_de_loki(dashboard_path: Path) -> None:
    """Impede dashboards versionados de dependerem de Loki sem backend provisionado."""
    text = dashboard_path.read_text()
    for forbidden in FORBIDDEN_STRINGS:
        assert forbidden not in text
