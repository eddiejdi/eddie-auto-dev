from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "homelab" / "tuya_token_selfheal.py"
_SPEC = importlib.util.spec_from_file_location("tuya_token_selfheal", MODULE_PATH)
assert _SPEC and _SPEC.loader
selfheal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(selfheal)

NOW_MS = 1_784_000_000_000

FRESH_TOKEN = {
    "access_token": "a",
    "refresh_token": "r",
    "expire_time": 7200,
    "t": NOW_MS - 60_000,
    "uid": "az1",
}
EXPIRED_TOKEN = {
    "access_token": "a",
    "refresh_token": "r",
    "expire_time": 7200,
    "t": NOW_MS - 100 * 3600 * 1000,
    "uid": "az1",
}


def test_token_expiry_ms() -> None:
    assert selfheal.token_expiry_ms(FRESH_TOKEN) == FRESH_TOKEN["t"] + 7200 * 1000
    assert selfheal.token_expiry_ms({}) == 0
    assert selfheal.token_expiry_ms({"t": "x", "expire_time": 1}) == 0


def test_token_remaining_minutes() -> None:
    remaining = selfheal.token_remaining_minutes(FRESH_TOKEN, now_ms=NOW_MS)
    assert remaining == pytest.approx(119, abs=1)
    assert selfheal.token_remaining_minutes(EXPIRED_TOKEN, now_ms=NOW_MS) < 0


def test_valid_runtime_token() -> None:
    assert selfheal.valid_runtime_token(FRESH_TOKEN)
    assert not selfheal.valid_runtime_token(None)
    assert not selfheal.valid_runtime_token({"access_token": "a"})
    assert not selfheal.valid_runtime_token([1, 2])


def test_should_heal_happy_path() -> None:
    heal, reason = selfheal.should_heal(
        EXPIRED_TOKEN, FRESH_TOKEN, entities_active=0, heals_last_24h=0, now_ms=NOW_MS
    )
    assert heal, reason


@pytest.mark.parametrize(
    ("ha_token", "runtime", "active", "heals", "expected_reason"),
    [
        (EXPIRED_TOKEN, FRESH_TOKEN, 5, 0, "entidades ativas"),
        (FRESH_TOKEN, FRESH_TOKEN, 0, 0, "ainda válido"),
        (EXPIRED_TOKEN, None, 0, 0, "ausente/inválido"),
        (EXPIRED_TOKEN, EXPIRED_TOKEN, 0, 0, "não é mais novo"),
        (EXPIRED_TOKEN, FRESH_TOKEN, 0, 3, "rate limit"),
    ],
)
def test_should_heal_guards(ha_token, runtime, active, heals, expected_reason) -> None:
    heal, reason = selfheal.should_heal(
        ha_token, runtime, entities_active=active, heals_last_24h=heals, now_ms=NOW_MS
    )
    assert not heal
    assert expected_reason in reason


def test_inject_token_replaces_only_tuya_entry() -> None:
    config = {
        "data": {
            "entries": [
                {"domain": "tuya_local", "data": {"device_id": "x"}},
                {"domain": "tuya", "data": {"token_info": EXPIRED_TOKEN, "user_code": "u"}},
            ]
        }
    }
    entry = selfheal.inject_token(config, FRESH_TOKEN)
    assert entry["data"]["token_info"] == FRESH_TOKEN
    assert entry["data"]["user_code"] == "u"
    assert config["data"]["entries"][0]["data"] == {"device_id": "x"}


def test_inject_token_missing_entry_raises() -> None:
    with pytest.raises(LookupError):
        selfheal.inject_token({"data": {"entries": []}}, FRESH_TOKEN)


def test_render_prom_format() -> None:
    out = selfheal.render_prom({"tuya_selfheal_healthy": 1, "tuya_entities_active": 53})
    assert "# TYPE tuya_selfheal_healthy gauge" in out
    assert "tuya_selfheal_healthy 1" in out
    assert "tuya_entities_active 53" in out
    assert out.endswith("\n")


def test_prune_heal_history() -> None:
    now = 1_784_000_000.0
    history = [now - 90_000, now - 3_600, now - 10]
    assert selfheal.prune_heal_history(history, now=now) == [now - 3_600, now - 10]
