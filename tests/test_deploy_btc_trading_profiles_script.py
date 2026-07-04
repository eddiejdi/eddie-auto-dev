"""Regression checks for the BTC trading deploy shell script."""

from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "deploy_btc_trading_profiles.sh"


def _load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_syncs_btc_dashboard_to_canonical_remote_filename() -> None:
    content = _load_script()
    assert 'BTC_DASHBOARD_SRC="${REPO_ROOT}/grafana/dashboards/btc-trading-monitor.json"' in content
    assert 'BTC_DASHBOARD_DST="${GRAFANA_PROVISIONING_DIR}/btc-trading-monitor.json"' in content
    assert "sync_btc_grafana_dashboard" in content


def test_script_archives_duplicate_btc_dashboard_files_before_grafana_restart() -> None:
    content = _load_script()
    assert '"${GRAFANA_PROVISIONING_DIR}/btc_trading_monitor.json"' in content
    assert '"${GRAFANA_PROVISIONING_DIR}/btc_trading_dashboard_v3_prometheus.json"' in content
    assert "dashboard_backups" in content
    assert "cleanup_btc_dashboard_duplicates" in content
    assert content.index("cleanup_btc_dashboard_duplicates") < content.index("restart_grafana_if_present")


def test_script_defaults_to_live_crypto_agent_service_user() -> None:
    content = _load_script()
    assert 'SERVICE_USER="${SERVICE_USER:-btc-trading}"' in content
    assert 'SERVICE_GROUP="${SERVICE_GROUP:-btc-trading}"' in content
    assert 'sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile' in content


def test_script_installs_canonical_btc_trading_sudoers_file() -> None:
    content = _load_script()
    assert "sudo rm -f /etc/sudoers.d/trading-svc-ollama" in content
    assert 'systemd/btc-trading-ollama.sudoers' in content
    assert "/etc/sudoers.d/btc-trading-ollama" in content
