import importlib.util
import os
import sys
import types
from pathlib import Path


def load_exporter_module():
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://postgres:test@localhost:5432/btc_trading",
    )
    sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *_a, **_k: None))
    path = Path(__file__).resolve().parents[1] / "grafana" / "exporters" / "trading_selfheal_exporter.py"
    spec = importlib.util.spec_from_file_location("trading_selfheal_exporter_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_runtime(root: Path):
    agent_dir = root / "btc_trading_agent"
    (agent_dir / "data" / "market_rag").mkdir(parents=True)
    (agent_dir / "models").mkdir()
    (agent_dir / "trading_agent.py").write_text(
        "def _annotate_blocked_decision():\n    pass\n",
        encoding="utf-8",
    )
    (agent_dir / "training_db.py").write_text(
        "def merge_decision_features():\n    pass\n",
        encoding="utf-8",
    )
    return agent_dir


def test_runtime_integrity_passes_with_patch_markers_and_writable_rag(tmp_path):
    mod = load_exporter_module()
    write_runtime(tmp_path)
    legacy_path = tmp_path / "missing_legacy"
    agent = mod.TradingAgentDef(
        symbol="BTC-USDT",
        profile="aggressive",
        systemd_unit="crypto-agent@BTC_USDT_aggressive",
        exporter_port=9092,
        config_file="config_BTC_USDT_aggressive.json",
        expected_process="trading_agent.py.*config_BTC_USDT_aggressive.json",
        runtime_root=str(tmp_path),
        legacy_path=str(legacy_path),
    )
    checker = mod.AgentHealthChecker([agent], "postgresql://postgres:test@localhost/test")
    state = mod.AgentState()

    assert checker.check_runtime_integrity(agent, state) is True
    assert state.runtime_path_ok is True
    assert state.runtime_patch_ok is True
    assert state.market_rag_writable is True
    assert state.legacy_path_present is False
    assert state.runtime_detail == ""


def test_runtime_integrity_fails_when_legacy_path_reappears(tmp_path):
    mod = load_exporter_module()
    write_runtime(tmp_path)
    legacy_path = tmp_path / "eddie-auto-dev"
    legacy_path.mkdir()
    agent = mod.TradingAgentDef(
        symbol="BTC-USDT",
        profile="conservative",
        systemd_unit="crypto-agent@BTC_USDT_conservative",
        exporter_port=9093,
        config_file="config_BTC_USDT_conservative.json",
        expected_process="trading_agent.py.*config_BTC_USDT_conservative.json",
        runtime_root=str(tmp_path),
        legacy_path=str(legacy_path),
    )
    checker = mod.AgentHealthChecker([agent], "postgresql://postgres:test@localhost/test")
    state = mod.AgentState()

    assert checker.check_runtime_integrity(agent, state) is False
    assert state.legacy_path_present is True
    assert "legacy_path_present" in state.runtime_detail


def test_runtime_integrity_fails_when_deployed_marker_is_missing(tmp_path):
    mod = load_exporter_module()
    agent_dir = write_runtime(tmp_path)
    (agent_dir / "trading_agent.py").write_text("# stale runtime file\n", encoding="utf-8")
    agent = mod.TradingAgentDef(
        symbol="USDT-BRL",
        profile="aggressive",
        systemd_unit="crypto-agent@USDT_BRL_aggressive",
        exporter_port=9094,
        config_file="config_USDT_BRL_aggressive.json",
        expected_process="trading_agent.py.*config_USDT_BRL_aggressive.json",
        runtime_root=str(tmp_path),
        legacy_path=str(tmp_path / "missing_legacy"),
    )
    checker = mod.AgentHealthChecker([agent], "postgresql://postgres:test@localhost/test")
    state = mod.AgentState()

    assert checker.check_runtime_integrity(agent, state) is False
    assert state.runtime_patch_ok is False
    assert "patch_marker_missing" in state.runtime_detail
