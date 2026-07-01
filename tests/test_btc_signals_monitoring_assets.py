"""Valida assets operacionais dos BTC leading signals."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMETHEUS_PATH = ROOT / "monitoring" / "prometheus.yml"
EXPORTER_PATH = ROOT / "grafana" / "exporters" / "btc_signals_exporter.py"


def test_prometheus_scrapes_btc_signals_exporter() -> None:
    text = PROMETHEUS_PATH.read_text(encoding="utf-8")

    assert "job_name: 'btc-signals-exporter'" in text
    assert "172.17.0.1:9123" in text
    assert "service: 'leading-signals'" in text


def test_btc_signals_exporter_exposes_funding_raw_metric() -> None:
    text = EXPORTER_PATH.read_text(encoding="utf-8")

    assert '_pset("btc_funding_raw"' in text
    assert "Average funding rate" in text
