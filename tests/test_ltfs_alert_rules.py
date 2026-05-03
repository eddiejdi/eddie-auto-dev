from pathlib import Path


RULES = Path("monitoring/prometheus/ltfs-selfheal-rules.yml").read_text(encoding="utf-8")
GRAFANA_RULES = Path("monitoring/grafana/provisioning/alerting/rules.yml").read_text(encoding="utf-8")


def test_prometheus_rules_include_nas_dependency_alerts() -> None:
    assert "alert: NASLTFSDependencyDown" in RULES
    assert 'homelab_nas_dependency_up{host="192.168.15.4",dependency="ltfs-ssh"} == 0' in RULES
    assert "alert: NASNodeExporterDown" in RULES
    assert 'up{job="nas-node-exporter",instance="rpa4all-nas-001"} == 0' in RULES


def test_grafana_rules_include_nas_dependency_alerts() -> None:
    assert "title: NASLTFSDependencyDown" in GRAFANA_RULES
    assert 'expr: homelab_nas_dependency_up{host="192.168.15.4",dependency="ltfs-ssh"}' in GRAFANA_RULES
    assert "title: NASNodeExporterDown" in GRAFANA_RULES
    assert 'expr: up{job="nas-node-exporter",instance="rpa4all-nas-001"}' in GRAFANA_RULES
