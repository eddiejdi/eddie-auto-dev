"""Regression checks for the BTC trading deploy workflow."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "workflows"
    / "deploy-btc-trading-profiles.yml"
)


def _load_workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_workflow_watches_slot_exit_runtime_files() -> None:
    content = _load_workflow()
    assert "btc_trading_agent/slot_exit_policy.py" in content
    assert "btc_trading_agent/profile_rules.py" in content
    assert "btc_trading_agent/position_manager_mixin.py" in content
    assert "btc_trading_agent/trading_agent.py" in content


def test_workflow_watches_dashboard_copies() -> None:
    content = _load_workflow()
    assert "grafana/btc_trading_dashboard_prometheus.json" in content
    assert "grafana/dashboards/btc_trading_monitor.json" in content


def test_workflow_validates_slot_based_tests_before_deploy() -> None:
    content = _load_workflow()
    assert "Validate slot-based BTC trading flow" in content
    assert "python3 -m py_compile" in content
    assert "tests/test_multi_entry_sell_behavior.py" in content
    assert "tests/unit/test_position_manager_mixin.py" in content
    assert "tests/test_grafana_dashboard_queries.py" in content
    assert "tests/test_deploy_btc_trading_profiles_script.py" in content
    assert content.index("Validate slot-based BTC trading flow") < content.index("Deploy optimized BTC profiles")
