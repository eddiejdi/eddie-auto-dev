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
config_subaccount_name = profile_rules.config_subaccount_name
open_buy_net_sql_predicate = profile_rules.open_buy_net_sql_predicate
live_config_shares_subaccount = profile_rules.live_config_shares_subaccount


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


def test_config_subaccount_name_strips_and_handles_missing() -> None:
    assert config_subaccount_name(None) == ""
    assert config_subaccount_name({}) == ""
    assert config_subaccount_name({"kucoin_subaccount_name": "  BTCConservative "}) == (
        "BTCConservative"
    )


def test_open_buy_net_sql_predicate_ignores_closed_and_reason() -> None:
    clause = open_buy_net_sql_predicate()
    assert "status <> 'closed'" in clause
    assert "closed_reason" in clause
    assert "external_deposit" not in clause
    with_dep = open_buy_net_sql_predicate(exclude_external_deposits=True)
    assert "external_deposit" in with_dep


def _live(profile: str, sub: str | None, **extra) -> dict:
    payload = {
        "enabled": True,
        "dry_run": False,
        "live_mode": True,
        "symbol": "BTC-USDT",
        "profile": profile,
    }
    if sub is not None:
        payload["kucoin_subaccount_name"] = sub
    payload.update(extra)
    return payload


def test_conservative_does_not_share_with_shadow_other_subaccount() -> None:
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="conservative",
        current_subaccount="BTCConservative",
        current_config_name="config_BTC_USDT_conservative.json",
        candidate_name="config_BTC_USDT_shadow.json",
        candidate=_live("shadow", "BTCAgressive"),
    ) is False


def test_aggressive_shares_with_shadow_same_subaccount() -> None:
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="aggressive",
        current_subaccount="BTCAgressive",
        current_config_name="config_BTC_USDT_aggressive.json",
        candidate_name="config_BTC_USDT_shadow.json",
        candidate=_live("shadow", "BTCAgressive"),
    ) is True


def test_empty_subaccount_never_shares() -> None:
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="conservative",
        current_subaccount="",
        current_config_name="config_BTC_USDT_conservative.json",
        candidate_name="config_BTC_USDT_shadow.json",
        candidate=_live("shadow", "BTCAgressive"),
    ) is False
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="conservative",
        current_subaccount="BTCConservative",
        current_config_name="config_BTC_USDT_conservative.json",
        candidate_name="config_BTC_USDT_aggressive.json",
        candidate=_live("aggressive", None),
    ) is False


def test_same_profile_or_dry_run_does_not_share() -> None:
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="conservative",
        current_subaccount="BTCConservative",
        current_config_name="config_BTC_USDT_conservative.json",
        candidate_name="config_conservative.json",
        candidate=_live("conservative", "BTCConservative"),
    ) is False
    assert live_config_shares_subaccount(
        current_symbol="BTC-USDT",
        current_profile="aggressive",
        current_subaccount="BTCAgressive",
        current_config_name="config_BTC_USDT_aggressive.json",
        candidate_name="config_BTC_USDT_shadow.json",
        candidate=_live("shadow", "BTCAgressive", dry_run=True),
    ) is False


def test_trading_agent_wires_shared_and_open_buy_helpers() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "btc_trading_agent"
        / "trading_agent.py"
    ).read_text(encoding="utf-8")
    assert "open_buy_net_sql_predicate" in src
    assert "live_config_shares_subaccount" in src
    assert "config_subaccount_name" in src
