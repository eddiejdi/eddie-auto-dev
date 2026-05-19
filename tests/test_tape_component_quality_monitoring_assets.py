"""Valida assets operacionais do Tape Component Quality."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "systemd" / "tape-component-quality-exporter.service"
PROMETHEUS_PATH = ROOT / "monitoring" / "prometheus.yml"
DASHBOARD_PATHS = [
    ROOT / "grafana" / "dashboards" / "tape-component-quality.json",
    ROOT / "monitoring" / "grafana" / "provisioning" / "dashboards" / "tape-component-quality-v1.json",
]
PLACEHOLDERS = ("${DS_PROMETHEUS}", "${datasource}")
FORBIDDEN_STRINGS = ("\"Loki\"", "\"type\": \"loki\"", "${DS_LOKI}")


def test_service_references_exporter_agent() -> None:
    text = SERVICE_PATH.read_text(encoding="utf-8")

    assert "tape_component_quality_agent.py --exporter" in text
    assert "9124" in text


def test_prometheus_contains_tape_component_job() -> None:
    text = PROMETHEUS_PATH.read_text(encoding="utf-8")

    assert "job_name: 'tape-component-quality'" in text
    assert "192.168.15.4:9124" in text
    assert "drive: 'host0-sg0'" in text


def test_dashboards_pin_real_tape_host() -> None:
    for dashboard_path in DASHBOARD_PATHS:
        text = dashboard_path.read_text(encoding="utf-8")
        assert 'tape_component_quality_overall_score{host=\\"rpa4all-nas-001\\",drive=\\"$drive\\"}' in text
        assert 'tape_component_quality_score{host=\\"rpa4all-nas-001\\",drive=\\"$drive\\",' in text


def test_dashboards_expose_drive_dropdown() -> None:
    for dashboard_path in DASHBOARD_PATHS:
        text = dashboard_path.read_text(encoding="utf-8")
        assert '"label": "Drive"' in text
        assert '"name": "drive"' in text
        assert 'label_values(tape_component_quality_overall_score{host=\\"rpa4all-nas-001\\"}, drive)' in text


def test_dashboards_are_valid_and_without_placeholders() -> None:
    for dashboard_path in DASHBOARD_PATHS:
        text = dashboard_path.read_text(encoding="utf-8")
        json.loads(text)
        for placeholder in PLACEHOLDERS:
            assert placeholder not in text
        for forbidden in FORBIDDEN_STRINGS:
            assert forbidden not in text
        assert '"uid": "dfc0w4yioe4u8e"' in text
