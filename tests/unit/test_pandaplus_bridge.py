"""Testes do bridge PandaPlus → Telegram.

Cobre:
- Carregamento de config a partir de env (BridgeConfig.from_env).
- Parsing de tokens do core.config_entries do HA.
- Classificação de eventos relevantes (alarm_lock, unlock_request).
- Endpoint HTTP de decisão: autorização, validação, idempotência.
- TTL/expiração de pedidos pendentes.

Não usa Tuya/Telegram reais — tudo mockado.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from tools.pandaplus_bridge import bridge as bridge_module
from tools.pandaplus_bridge.bridge import (
    DOOR_ALARM_VALUES,
    RELEVANT_CODES,
    PandaplusBridge,
    PendingRequest,
)
from tools.pandaplus_bridge.config import BridgeConfig, load_tuya_tokens
from tools.pandaplus_bridge.tuya_client import TuyaBridgeClient, TuyaStatusEvent


@pytest.fixture
def env_minimal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configura env mínimo válido para BridgeConfig.from_env."""
    storage = tmp_path / "core.config_entries"
    storage.write_text(
        json.dumps(
            {
                "data": {
                    "entries": [
                        {
                            "domain": "tuya",
                            "data": {
                                "endpoint": "https://apigw.tuyaus.com",
                                "terminal_id": "term123",
                                "user_code": "Ba0osdh",
                                "token_info": {
                                    "access_token": "a" * 32,
                                    "refresh_token": "r" * 32,
                                    "expire_time": 7200,
                                    "t": 1779700913679,
                                    "uid": "u" * 20,
                                },
                            },
                        }
                    ]
                }
            }
        )
    )
    monkeypatch.setenv("PANDAPLUS_DEVICE_ID", "eb24b140cebde5a9dd7abw")
    monkeypatch.setenv("PANDAPLUS_HA_STORAGE", str(storage))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:ABCDEF")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "948686300")
    return storage


# --- config ---

def test_bridge_config_from_env_defaults(env_minimal: Path) -> None:
    cfg = BridgeConfig.from_env()
    assert cfg.device_id == "eb24b140cebde5a9dd7abw"
    assert cfg.telegram_chat_id == 948686300
    assert cfg.allowed_user_ids == frozenset({948686300})
    assert cfg.observe_only is True
    assert cfg.reply_listen_port == 8590
    assert cfg.tuya_client_id == "HA_3y9q4ak7g4ephrvke"


def test_bridge_config_allowed_users_custom(
    env_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PANDAPLUS_ALLOWED_USERS", "111,222, 333")
    cfg = BridgeConfig.from_env()
    assert cfg.allowed_user_ids == frozenset({111, 222, 333})


def test_bridge_config_observe_off(
    env_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PANDAPLUS_OBSERVE_ONLY", "0")
    cfg = BridgeConfig.from_env()
    assert cfg.observe_only is False


def test_bridge_config_missing_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PANDAPLUS_DEVICE_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    with pytest.raises(ValueError, match="PANDAPLUS_DEVICE_ID"):
        BridgeConfig.from_env()


def test_bridge_config_invalid_chat_id(
    env_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "not_a_number")
    with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID inválido"):
        BridgeConfig.from_env()


def test_bridge_config_zero_chat_id(
    env_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "0")
    with pytest.raises(ValueError, match="não pode ser zero"):
        BridgeConfig.from_env()


def test_bridge_config_invalid_allowed_users(
    env_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PANDAPLUS_ALLOWED_USERS", "abc,123")
    with pytest.raises(ValueError, match="PANDAPLUS_ALLOWED_USERS"):
        BridgeConfig.from_env()


# --- load_tuya_tokens ---

def test_load_tuya_tokens_ok(env_minimal: Path) -> None:
    data = load_tuya_tokens(env_minimal)
    assert data["endpoint"] == "https://apigw.tuyaus.com"
    assert data["terminal_id"] == "term123"


def test_load_tuya_tokens_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tuya_tokens(tmp_path / "nao_existe.json")


def test_load_tuya_tokens_no_tuya_entry(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"data": {"entries": [{"domain": "mqtt"}]}}))
    with pytest.raises(KeyError, match="Nenhuma entry Tuya"):
        load_tuya_tokens(p)


def test_load_tuya_tokens_incomplete(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(
        json.dumps(
            {
                "data": {
                    "entries": [
                        {"domain": "tuya", "data": {"endpoint": "x"}}
                    ]
                }
            }
        )
    )
    with pytest.raises(KeyError, match="Entry Tuya incompleta"):
        load_tuya_tokens(p)


def test_load_runtime_tokens_ok(tmp_path: Path) -> None:
    p = tmp_path / "runtime.json"
    p.write_text(
        json.dumps(
            {
                "access_token": "a",
                "refresh_token": "r",
                "expire_time": 7200,
                "t": 1779700913679,
                "uid": "uid1",
            }
        )
    )
    loaded = PandaplusBridge._load_runtime_tokens(p)
    assert loaded is not None
    assert loaded["refresh_token"] == "r"


def test_load_runtime_tokens_invalid(tmp_path: Path) -> None:
    p = tmp_path / "runtime.json"
    p.write_text(json.dumps({"access_token": "a"}))
    assert PandaplusBridge._load_runtime_tokens(p) is None


def test_token_expiry_ms() -> None:
    expiry = PandaplusBridge._token_expiry_ms({"t": 1000, "expire_time": 2})
    assert expiry == 3000


def test_build_poll_events_baseline_no_event() -> None:
    update_time, status_map, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 100,
            "status": [
                {"code": "alarm_lock", "value": "wrong_finger"},
                {"code": "unlock_fingerprint", "value": 1},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {},
        None,
    )
    assert update_time == 100
    assert status_map["alarm_lock"] == "wrong_finger"
    assert events == []


def test_build_poll_events_emits_alarm_on_value_change() -> None:
    _, _, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 200,
            "status": [
                {"code": "alarm_lock", "value": "wrong_finger"},
                {"code": "unlock_fingerprint", "value": 1},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {"alarm_lock": "", "unlock_fingerprint": 0},
        100,
    )
    assert len(events) == 1
    assert events[0].code == "alarm_lock"
    assert events[0].value == "wrong_finger"
    assert events[0].raw["source"] == "poll"


def test_build_poll_events_emits_alarm_when_activity_changes() -> None:
    _, _, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 210,
            "status": [
                {"code": "alarm_lock", "value": "wrong_finger"},
                {"code": "unlock_fingerprint", "value": 2},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {"alarm_lock": "wrong_finger", "unlock_fingerprint": 1},
        200,
    )
    assert len(events) == 1
    assert events[0].code == "alarm_lock"
    assert events[0].value == "wrong_finger"


def test_build_poll_events_emits_unlock_request_change() -> None:
    _, _, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 300,
            "status": [
                {"code": "unlock_request", "value": 45},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {"unlock_request": 0},
        250,
    )
    assert len(events) == 1
    assert events[0].code == "unlock_request"
    assert events[0].value == 45


def test_build_poll_events_emits_change_even_without_update_time_increment() -> None:
    _, _, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 300,
            "status": [
                {"code": "unlock_request", "value": 81},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {"unlock_request": 45},
        300,
    )
    assert len(events) == 1
    assert events[0].code == "unlock_request"
    assert events[0].value == 81


def test_build_poll_events_no_change_with_static_update_time() -> None:
    _, _, events = TuyaBridgeClient.build_poll_events(
        "dev1",
        {
            "update_time": 300,
            "status": [
                {"code": "unlock_request", "value": 81},
                {"code": "unlock_fingerprint", "value": 2},
            ],
        },
        frozenset({"alarm_lock", "unlock_request"}),
        {"unlock_request": 81, "unlock_fingerprint": 2},
        300,
    )
    assert events == []


# --- PendingRequest ---

def test_pending_request_not_expired() -> None:
    p = PendingRequest(
        token="t", device_id="d", created_at=time.time(), ttl_seconds=60
    )
    assert p.is_expired() is False


def test_pending_request_expired() -> None:
    p = PendingRequest(
        token="t", device_id="d", created_at=time.time() - 120, ttl_seconds=60
    )
    assert p.is_expired() is True


# --- event classification ---

def test_relevant_codes_set() -> None:
    assert "unlock_request" in RELEVANT_CODES
    assert "alarm_lock" in RELEVANT_CODES
    assert "battery_state" not in RELEVANT_CODES


def test_door_alarm_values() -> None:
    assert "wrong_finger" in DOOR_ALARM_VALUES
    assert "low_battery" not in DOOR_ALARM_VALUES


# --- bridge event handling ---

@pytest.fixture
def mock_bridge(env_minimal: Path) -> PandaplusBridge:
    cfg = BridgeConfig.from_env()
    b = PandaplusBridge(cfg)
    b._telegram = AsyncMock()
    b._telegram.send_unlock_request = AsyncMock(
        return_value={"message_id": 42}
    )
    b._telegram.send_event = AsyncMock(return_value={"message_id": 1})
    b._telegram.edit_message = AsyncMock(return_value={})
    b._tuya = MagicMock()
    b._tuya.reply_unlock_request = AsyncMock(
        return_value={"success": True}
    )
    return b


@pytest.mark.asyncio
async def test_handle_event_unlock_request_creates_pending(
    mock_bridge: PandaplusBridge,
) -> None:
    ev = TuyaStatusEvent(
        device_id="eb24b140cebde5a9dd7abw",
        code="unlock_request",
        value=45,
        raw={},
    )
    await mock_bridge._handle_event(ev)
    assert len(mock_bridge._pending) == 1
    pending = next(iter(mock_bridge._pending.values()))
    assert pending.unlock_request_seconds == 45
    assert pending.alarm is None
    mock_bridge._telegram.send_unlock_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_event_alarm_lock_creates_pending(
    mock_bridge: PandaplusBridge,
) -> None:
    ev = TuyaStatusEvent(
        device_id="eb24b140cebde5a9dd7abw",
        code="alarm_lock",
        value="wrong_finger",
        raw={},
    )
    await mock_bridge._handle_event(ev)
    assert len(mock_bridge._pending) == 1
    pending = next(iter(mock_bridge._pending.values()))
    assert pending.alarm == "wrong_finger"
    assert pending.unlock_request_seconds == 0


@pytest.mark.asyncio
async def test_handle_event_unlock_request_zero_ignored(
    mock_bridge: PandaplusBridge,
) -> None:
    ev = TuyaStatusEvent(
        device_id="x", code="unlock_request", value=0, raw={}
    )
    await mock_bridge._handle_event(ev)
    assert len(mock_bridge._pending) == 0


@pytest.mark.asyncio
async def test_handle_event_irrelevant_code_ignored(
    mock_bridge: PandaplusBridge,
) -> None:
    ev = TuyaStatusEvent(
        device_id="x", code="battery_state", value="low", raw={}
    )
    await mock_bridge._handle_event(ev)
    assert len(mock_bridge._pending) == 0


@pytest.mark.asyncio
async def test_handle_event_alarm_lock_irrelevant_value(
    mock_bridge: PandaplusBridge,
) -> None:
    """alarm_lock=low_battery não dispara notificação."""
    ev = TuyaStatusEvent(
        device_id="x", code="alarm_lock", value="low_battery", raw={}
    )
    await mock_bridge._handle_event(ev)
    assert len(mock_bridge._pending) == 0


@pytest.mark.asyncio
async def test_gc_pending_removes_expired(
    mock_bridge: PandaplusBridge,
) -> None:
    expired = PendingRequest(
        token="exp",
        device_id="d",
        created_at=time.time() - 9999,
        ttl_seconds=60,
        telegram_message_id=10,
        chat_id=948686300,
    )
    fresh = PendingRequest(
        token="ok",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
    )
    mock_bridge._pending = {"exp": expired, "ok": fresh}
    await mock_bridge._gc_pending()
    assert "exp" not in mock_bridge._pending
    assert "ok" in mock_bridge._pending
    mock_bridge._telegram.edit_message.assert_awaited_once()


# --- HTTP reply handler ---

@pytest.mark.asyncio
async def test_http_reply_handler_unauthorized(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="abc",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
    )
    mock_bridge._pending["abc"] = pending

    req = MagicMock()
    req.json = AsyncMock(
        return_value={"token": "abc", "decision": "approve", "user_id": 999}
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 403


@pytest.mark.asyncio
async def test_http_reply_handler_approve_ok(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="abc",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
        telegram_message_id=42,
        chat_id=948686300,
    )
    mock_bridge._pending["abc"] = pending

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "abc",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 200
    mock_bridge._tuya.reply_unlock_request.assert_awaited_once_with(True)
    assert pending.decided is True
    assert pending.decided_by == 948686300


@pytest.mark.asyncio
async def test_http_reply_handler_deny_ok(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="xyz",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
    )
    mock_bridge._pending["xyz"] = pending

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "xyz",
            "decision": "deny",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 200
    mock_bridge._tuya.reply_unlock_request.assert_awaited_once_with(False)
    assert pending.decided is False


@pytest.mark.asyncio
async def test_http_reply_handler_unknown_token(
    mock_bridge: PandaplusBridge,
) -> None:
    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "ghost",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 404


@pytest.mark.asyncio
async def test_http_reply_handler_expired(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="old",
        device_id="d",
        created_at=time.time() - 9999,
        ttl_seconds=60,
    )
    mock_bridge._pending["old"] = pending

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "old",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 410


@pytest.mark.asyncio
async def test_http_reply_handler_already_decided(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="dup",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
        decided=True,
        decided_by=948686300,
    )
    mock_bridge._pending["dup"] = pending

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "dup",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 409


@pytest.mark.asyncio
async def test_http_reply_handler_invalid_payload(
    mock_bridge: PandaplusBridge,
) -> None:
    req = MagicMock()
    req.json = AsyncMock(side_effect=ValueError("invalid"))
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_http_reply_handler_missing_fields(
    mock_bridge: PandaplusBridge,
) -> None:
    req = MagicMock()
    req.json = AsyncMock(return_value={"token": "x"})
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_http_reply_handler_tuya_failure(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="fail",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
    )
    mock_bridge._pending["fail"] = pending
    mock_bridge._tuya.reply_unlock_request = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "fail",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 502


@pytest.mark.asyncio
async def test_http_reply_handler_tuya_unavailable(
    mock_bridge: PandaplusBridge,
) -> None:
    pending = PendingRequest(
        token="down",
        device_id="d",
        created_at=time.time(),
        ttl_seconds=60,
    )
    mock_bridge._pending["down"] = pending
    mock_bridge._tuya = None

    req = MagicMock()
    req.json = AsyncMock(
        return_value={
            "token": "down",
            "decision": "approve",
            "user_id": 948686300,
        }
    )
    resp = await mock_bridge._http_reply_handler(req)
    assert resp.status == 503


@pytest.mark.asyncio
async def test_poll_tuya_fallback_processes_events(
    mock_bridge: PandaplusBridge,
) -> None:
    ev = TuyaStatusEvent(
        device_id="eb24b140cebde5a9dd7abw",
        code="alarm_lock",
        value="wrong_finger",
        raw={"source": "poll"},
    )
    mock_bridge._tuya.poll_status_changes = AsyncMock(return_value=[ev])

    await mock_bridge._poll_tuya_fallback()

    mock_bridge._telegram.send_unlock_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_http_health_handler(mock_bridge: PandaplusBridge) -> None:
    resp = await mock_bridge._http_health_handler(MagicMock())
    assert resp.status == 200


def test_coerce_int() -> None:
    assert PandaplusBridge._coerce_int(42) == 42
    assert PandaplusBridge._coerce_int("17") == 17
    assert PandaplusBridge._coerce_int("nope") == 0
    assert PandaplusBridge._coerce_int(None) == 0


def test_record_tuya_success_resets_failure_state(
    mock_bridge: PandaplusBridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge_module, "PROM_FILE", tmp_path / "bridge.prom")
    mock_bridge._tuya_consecutive_failures = 3
    mock_bridge._tuya_last_healthy_ts = 0.0

    mock_bridge._record_tuya_success()

    assert mock_bridge._tuya_consecutive_failures == 0
    assert mock_bridge._tuya_last_healthy_ts > 0
    prom_content = (tmp_path / "bridge.prom").read_text(encoding="utf-8")
    assert "pandaplus_bridge_tuya_session_healthy 1" in prom_content


def test_record_tuya_failure_below_threshold_does_not_raise(
    mock_bridge: PandaplusBridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge_module, "PROM_FILE", tmp_path / "bridge.prom")
    mock_bridge._tuya_last_healthy_ts = time.time()

    mock_bridge._record_tuya_failure()  # não deve levantar

    assert mock_bridge._tuya_consecutive_failures == 1
    prom_content = (tmp_path / "bridge.prom").read_text(encoding="utf-8")
    assert "pandaplus_bridge_tuya_session_healthy 0" in prom_content


def test_record_tuya_failure_above_threshold_raises_stuck_error(
    mock_bridge: PandaplusBridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge_module, "PROM_FILE", tmp_path / "bridge.prom")
    # sessão saudável pela última vez bem além do limite configurado
    mock_bridge._tuya_last_healthy_ts = (
        time.time() - bridge_module.TUYA_UNHEALTHY_RESTART_SECONDS - 1
    )

    with pytest.raises(bridge_module.TuyaSessionStuckError):
        mock_bridge._record_tuya_failure()


@pytest.mark.asyncio
async def test_tuya_supervisor_loop_propagates_stuck_error(
    mock_bridge: PandaplusBridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O loop supervisor deve deixar TuyaSessionStuckError escapar (não engolir)."""
    monkeypatch.setattr(bridge_module, "PROM_FILE", tmp_path / "bridge.prom")
    mock_bridge._tuya = MagicMock()
    mock_bridge._tuya.session_check = MagicMock(
        side_effect=Exception("network error:(-9999999) sign invalid")
    )
    mock_bridge._tuya_last_healthy_ts = (
        time.time() - bridge_module.TUYA_UNHEALTHY_RESTART_SECONDS - 1
    )

    with pytest.raises(bridge_module.TuyaSessionStuckError):
        await mock_bridge._tuya_supervisor_loop()
