from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = ROOT / "grafana" / "dashboards" / "nas-rpa4all-omv.json"
ASSESSOR_PATH = ROOT / "tools" / "homelab" / "nas_ai_assessor.py"


def load_dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def get_panel(panel_id: int) -> dict:
    for panel in load_dashboard()["panels"]:
        if panel.get("id") == panel_id:
            return panel
    raise AssertionError(f"panel {panel_id} not found")


def get_exprs(panel_id: int) -> list[str]:
    return [t["expr"] for t in get_panel(panel_id).get("targets", []) if "expr" in t]


def test_ltfs_service_and_timeouts_use_current_service_label() -> None:
    assert 'service="ltfs-lto6.service"' in get_exprs(10)[0]
    assert 'exported_service=' not in get_exprs(10)[0]
    assert 'service="ltfs-lto6.service"' in get_exprs(16)[0]
    assert 'exported_service=' not in get_exprs(16)[0]


def test_tape_stat_panels_do_not_hardcode_device_serials() -> None:
    for panel_id in (24, 25, 26):
        expr = get_exprs(panel_id)[0]
        assert 'device=' not in expr
        assert expr.startswith("max(")


def test_buffer_panel_uses_flush_buffer_metrics_in_percent() -> None:
    panel = get_panel(28)
    exprs = get_exprs(28)
    assert panel["title"] == "Buffer Occupancy Trend"
    assert panel["fieldConfig"]["defaults"]["unit"] == "percent"
    assert "homelab_ltfs_flush_buffer_usage_percent" in exprs[0]
    assert "100 - homelab_ltfs_flush_buffer_usage_percent" in exprs[1]


def test_bind_mount_panel_uses_dashboard_instance_variable() -> None:
    assert 'instance="$instance"' in get_exprs(21)[0]


def test_nas_ai_assessor_defaults_match_dashboard_layout_and_queries() -> None:
    text = ASSESSOR_PATH.read_text(encoding="utf-8")
    assert 'GRAFANA_PANEL_ID = int(os.environ.get("GRAFANA_PANEL_ID", "31"))' in text
    assert 'service="ltfs-lto6.service"' in text
    assert 'exported_service=' not in text
    assert 'max(nas_tape_drive_ready' in text
    assert 'max(nas_tape_medium_loaded' in text
    assert 'max(nas_tape_compression_enabled' in text
