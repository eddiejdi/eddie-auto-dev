import importlib.util
from pathlib import Path


def _load_validate_btc_config():
    path = Path(__file__).resolve().parents[1] / "systemd" / "validate_btc_config.py"
    spec = importlib.util.spec_from_file_location("validate_btc_config_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


validate_btc_config = _load_validate_btc_config()
resolve_config_path = validate_btc_config.resolve_config_path
validate_config_payload = validate_btc_config.validate_config_payload


def test_resolve_config_path_uses_coin_config_file_env(monkeypatch) -> None:
    monkeypatch.setenv("COIN_CONFIG_FILE", "config_BTC_USDT_conservative.json")
    path = resolve_config_path([])
    assert path.name == "config_BTC_USDT_conservative.json"


def test_validate_config_payload_rejects_btc_default_profile() -> None:
    payload = {
        "dry_run": False,
        "symbol": "BTC-USDT",
        "risk_management": {},
        "max_daily_loss": 10,
        "max_daily_trades": 20,
        "notifications": {},
    }
    errors = validate_config_payload(payload, config_name="config.json")
    assert any("BTC-USDT requires profile" in err for err in errors)


def test_validate_config_payload_accepts_btc_dual_profile() -> None:
    payload = {
        "dry_run": False,
        "symbol": "BTC-USDT",
        "profile": "aggressive",
        "risk_management": {},
        "max_daily_loss": 10,
        "max_daily_trades": 20,
        "notifications": {},
    }
    errors = validate_config_payload(payload, config_name="config_BTC_USDT_aggressive.json")
    assert errors == []
