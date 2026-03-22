from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_nas_dashboard_has_expected_uid_and_metrics() -> None:
    dashboard_path = ROOT / "grafana" / "dashboards" / "nas-rpa4all-omv.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))

    assert dashboard["uid"] == "nas-rpa4all-omv"
    assert dashboard["title"] == "NAS RPA4All - OMV Monitor"

    panel_exprs = []
    for panel in dashboard["panels"]:
        for target in panel.get("targets") or []:
            expr = target.get("expr")
            if expr:
                panel_exprs.append(expr)

    assert any("up{job=\"nas-node-exporter\"" in expr for expr in panel_exprs)
    assert any("node_cpu_seconds_total" in expr for expr in panel_exprs)
    assert any("node_memory_MemAvailable_bytes" in expr for expr in panel_exprs)
    assert any("node_filesystem_avail_bytes" in expr for expr in panel_exprs)
    assert any("nas_ltfs_mount_up" in expr for expr in panel_exprs)
    assert any("nas_ltfs_read_only" in expr for expr in panel_exprs)
    assert any("nas_ltfs_used_bytes" in expr for expr in panel_exprs)
    assert any("nas_ltfs_write_timeout_events_24h" in expr for expr in panel_exprs)
    assert any("nas_fc_abort_events_24h" in expr for expr in panel_exprs)
    assert any("nas_ltfs_selfheal_last_result_code" in expr for expr in panel_exprs)
    assert any("nas_ltfs_selfheal_attempts_24h" in expr for expr in panel_exprs)
    assert any("nas_ltfs_selfheal_consecutive_failures" in expr for expr in panel_exprs)


def test_prometheus_config_includes_nas_scrape_job() -> None:
    prom_path = ROOT / "monitoring" / "prometheus.yml"
    content = prom_path.read_text(encoding="utf-8")

    assert "job_name: 'nas-node-exporter'" in content
    assert "targets: ['192.168.15.4:9100']" in content
    assert "service: 'omv-nas'" in content


def test_grafana_rules_include_nas_alerts() -> None:
    rules_path = ROOT / "monitoring" / "grafana" / "provisioning" / "alerting" / "rules.yml"
    content = rules_path.read_text(encoding="utf-8")

    assert "name: NAS - OMV Alerts" in content
    assert "title: NAS Node Exporter Down" in content
    assert "title: NAS CPU High" in content
    assert "title: NAS Memory High" in content
    assert "title: NAS Root Filesystem High" in content
    assert "title: NAS LTFS Read Only" in content
    assert "title: NAS LTFS Self-Heal Failing" in content
    assert "title: NAS LTFS Write Timeouts" in content
    assert "title: NAS FC Abort Events" in content


def test_lto6_metric_export_assets_exist() -> None:
    assert (ROOT / "tools" / "nas" / "export_lto6_metrics.sh").exists()
    assert (ROOT / "tools" / "nas" / "lto6_selfheal.sh").exists()
    assert (ROOT / "systemd" / "lto6-metrics-export.service").exists()
    assert (ROOT / "systemd" / "lto6-metrics-export.timer").exists()
    assert (ROOT / "systemd" / "lto6-selfheal.service").exists()
    assert (ROOT / "systemd" / "lto6-selfheal.timer").exists()
