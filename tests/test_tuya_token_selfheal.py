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
# ~30 min remaining with default soft=45 → inside soft window
NEAR_EXPIRY_TOKEN = {
    "access_token": "a-old",
    "refresh_token": "r-old",
    "expire_time": 7200,
    "t": NOW_MS - 90 * 60 * 1000,
    "uid": "az1",
}
# Newer than NEAR_EXPIRY (~100 min remaining)
NEWER_RUNTIME = {
    "access_token": "a-new",
    "refresh_token": "r-new",
    "expire_time": 7200,
    "t": NOW_MS - 20 * 60 * 1000,
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
    near = selfheal.token_remaining_minutes(NEAR_EXPIRY_TOKEN, now_ms=NOW_MS)
    assert 25 < near < 35


def test_valid_runtime_token() -> None:
    assert selfheal.valid_runtime_token(FRESH_TOKEN)
    assert not selfheal.valid_runtime_token(None)
    assert not selfheal.valid_runtime_token({"access_token": "a"})
    assert not selfheal.valid_runtime_token([1, 2])


def test_should_heal_expired_with_active_entities() -> None:
    """Estado zumbi: token expirado mas entidades ainda 'ativas' no cache."""
    heal, reason = selfheal.should_heal(
        EXPIRED_TOKEN,
        FRESH_TOKEN,
        entities_active=75,
        heals_last_24h=0,
        now_ms=NOW_MS,
        soft_threshold_min=45,
    )
    assert heal, reason
    assert "expirado" in reason


def test_should_heal_soft_threshold_with_newer_bridge() -> None:
    heal, reason = selfheal.should_heal(
        NEAR_EXPIRY_TOKEN,
        NEWER_RUNTIME,
        entities_active=75,
        heals_last_24h=0,
        now_ms=NOW_MS,
        soft_threshold_min=45,
    )
    assert heal, reason
    assert "expira em" in reason


def test_should_heal_soft_skips_when_bridge_not_newer() -> None:
    heal, reason = selfheal.should_heal(
        NEAR_EXPIRY_TOKEN,
        NEAR_EXPIRY_TOKEN,
        entities_active=75,
        heals_last_24h=0,
        now_ms=NOW_MS,
        soft_threshold_min=45,
    )
    assert not heal
    assert "não é mais novo" in reason


def test_should_heal_still_valid_above_soft() -> None:
    heal, reason = selfheal.should_heal(
        FRESH_TOKEN,
        NEWER_RUNTIME,
        entities_active=0,
        heals_last_24h=0,
        now_ms=NOW_MS,
        soft_threshold_min=45,
    )
    assert not heal
    assert "ainda válido" in reason


@pytest.mark.parametrize(
    ("ha_token", "runtime", "active", "heals", "expected_reason"),
    [
        (FRESH_TOKEN, FRESH_TOKEN, 0, 0, "ainda válido"),
        (EXPIRED_TOKEN, None, 0, 0, "ausente/inválido"),
        (EXPIRED_TOKEN, EXPIRED_TOKEN, 0, 0, "não é mais novo"),
        (EXPIRED_TOKEN, FRESH_TOKEN, 0, 24, "rate limit"),
    ],
)
def test_should_heal_guards(ha_token, runtime, active, heals, expected_reason) -> None:
    heal, reason = selfheal.should_heal(
        ha_token,
        runtime,
        entities_active=active,
        heals_last_24h=heals,
        now_ms=NOW_MS,
        soft_threshold_min=45,
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


def test_ha_status_with_retry_returns_none_on_persistent_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def boom() -> dict:
        calls["n"] += 1
        raise TimeoutError("docker exec lento")

    monkeypatch.setattr(selfheal, "ha_tuya_status", boom)
    assert selfheal.ha_tuya_status_with_retry(attempts=3, backoff_s=0) is None
    assert calls["n"] == 3


def test_ha_status_with_retry_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [TimeoutError("lento"), {"entities_active": 5}]

    def flaky() -> dict:
        r = results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(selfheal, "ha_tuya_status", flaky)
    assert selfheal.ha_tuya_status_with_retry(attempts=2, backoff_s=0) == {
        "entities_active": 5
    }


def test_prune_heal_history() -> None:
    now = 1_784_000_000.0
    history = [now - 90_000, now - 3_600, now - 10]
    assert selfheal.prune_heal_history(history, now=now) == [now - 3_600, now - 10]


def test_ensure_fresh_runtime_skips_when_ha_has_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    def boom(*_a, **_k):  # noqa: ANN001
        called["n"] += 1
        raise AssertionError("não deve refreshar")

    monkeypatch.setattr(selfheal, "force_refresh_token", boom)
    out = selfheal.ensure_fresh_runtime_token(
        FRESH_TOKEN, NEWER_RUNTIME, soft_threshold_min=45, now_ms=NOW_MS
    )
    assert out == NEWER_RUNTIME
    assert called["n"] == 0


def test_ensure_fresh_runtime_refreshes_when_soft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refreshed = {
        "access_token": "a-ref",
        "refresh_token": "r-ref",
        "expire_time": 7200,
        "t": NOW_MS + 1_000,
        "uid": "az1",
    }
    persisted: list[dict] = []

    monkeypatch.setattr(
        selfheal,
        "load_tuya_entry_meta",
        lambda: {"user_code": "Ba0osdh", "endpoint": "https://apigw.tuyaus.com"},
    )
    monkeypatch.setattr(selfheal, "force_refresh_token", lambda *a, **k: refreshed)
    monkeypatch.setattr(selfheal, "persist_runtime_token", lambda t: persisted.append(t))

    out = selfheal.ensure_fresh_runtime_token(
        NEAR_EXPIRY_TOKEN,
        NEAR_EXPIRY_TOKEN,
        soft_threshold_min=45,
        now_ms=NOW_MS,
    )
    assert out == refreshed
    assert persisted == [refreshed]


def test_ensure_fresh_uses_existing_newer_runtime_without_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Runtime mais novo com folga > soft — não chama force_refresh.
    rich_runtime = {
        "access_token": "a-rich",
        "refresh_token": "r-rich",
        "expire_time": 7200,
        "t": NOW_MS - 5 * 60 * 1000,  # ~115 min remaining
        "uid": "az1",
    }
    monkeypatch.setattr(
        selfheal,
        "force_refresh_token",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no refresh")),
    )
    out = selfheal.ensure_fresh_runtime_token(
        NEAR_EXPIRY_TOKEN,
        rich_runtime,
        soft_threshold_min=45,
        now_ms=NOW_MS,
    )
    assert out == rich_runtime


def test_default_soft_threshold_is_45() -> None:
    assert selfheal.HEAL_SOFT_THRESHOLD_MIN == 45
