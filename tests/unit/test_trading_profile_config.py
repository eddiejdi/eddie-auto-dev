from pathlib import Path
import json

import pytest


def _load_agent_config(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "btc_trading_agent" / filename
    return json.loads(config_path.read_text(encoding="utf-8"))


def test_aggressive_profile_config_is_more_exposed() -> None:
    config = _load_agent_config("config_BTC_USDT_aggressive.json")
    assert config["max_position_pct"] == pytest.approx(1.0)
    assert config["min_trade_interval"] == 600


def test_conservative_profile_config_increases_exposure() -> None:
    config = _load_agent_config("config_BTC_USDT_conservative.json")
    assert config["max_position_pct"] == pytest.approx(0.6)
    assert config["min_trade_interval"] == 900
