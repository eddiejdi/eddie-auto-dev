from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_nextcloud_dashboard_has_expected_uid_and_metrics() -> None:
    dashboard_path = ROOT / "grafana" / "dashboards" / "nextcloud-rpa4all-selfheal.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))

    assert dashboard["uid"] == "nextcloud-rpa4all-selfheal"
    assert dashboard["title"] == "Nextcloud RPA4All - Health & Self-Healing"

    panel_exprs = []
    for panel in dashboard["panels"]:
        for target in panel.get("targets") or []:
            expr = target.get("expr")
            if expr:
                panel_exprs.append(expr)

    assert any("nextcloud_overall_health" in expr for expr in panel_exprs)
    assert any("nextcloud_probe_up" in expr for expr in panel_exprs)
    assert any("nextcloud_container_healthy" in expr for expr in panel_exprs)
    assert any("nextcloud_selfheal_actions_total" in expr for expr in panel_exprs)


def test_nextcloud_exporter_config_contains_public_and_local_probes() -> None:
    config_path = ROOT / "grafana" / "exporters" / "nextcloud_selfheal_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    probes = {item["name"]: item for item in config["probes"]}
    assert probes["public_status"]["url"] == "https://nextcloud.rpa4all.com/status.php"
    assert probes["local_status"]["url"] == "http://127.0.0.1:8880/status.php"
    assert probes["public_login"]["method"] == "POST"
    assert config["edge_restart_command"] == "systemctl restart cloudflared-rpa4all.service"


def test_grafana_rules_include_nextcloud_alerts() -> None:
    rules_path = ROOT / "monitoring" / "grafana" / "provisioning" / "alerting" / "rules.yml"
    content = rules_path.read_text(encoding="utf-8")

    assert "name: Nextcloud - RPA4All Alerts" in content
    assert "title: Nextcloud Public Endpoint Down" in content
    assert "title: Nextcloud Login Flow Down" in content
    assert "title: Nextcloud Self-Healing Exhausted" in content
