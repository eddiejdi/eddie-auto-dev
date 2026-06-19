import importlib.util
from pathlib import Path


def _load_profile_rules():
    path = Path(__file__).resolve().parents[1] / "btc_trading_agent" / "profile_rules.py"
    spec = importlib.util.spec_from_file_location("profile_rules_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


profile_rules = _load_profile_rules()
normalize_profile = profile_rules.normalize_profile
validate_profile_for_symbol = profile_rules.validate_profile_for_symbol


def test_normalize_profile_defaults_to_default() -> None:
    assert normalize_profile(None) == "default"
    assert normalize_profile("") == "default"


def test_btc_rejects_default_profile() -> None:
    try:
        validate_profile_for_symbol("BTC-USDT", "default", config_name="config.json")
    except ValueError as exc:
        assert "BTC-USDT requires profile" in str(exc)
        assert "config.json" in str(exc)
    else:
        raise AssertionError("expected ValueError for BTC-USDT default profile")


def test_btc_accepts_dual_profiles() -> None:
    assert validate_profile_for_symbol("BTC-USDT", "conservative") == "conservative"
    assert validate_profile_for_symbol("BTC-USDT", "aggressive") == "aggressive"


def test_non_btc_keeps_default_profile() -> None:
    assert validate_profile_for_symbol("ETH-USDT", "default") == "default"
