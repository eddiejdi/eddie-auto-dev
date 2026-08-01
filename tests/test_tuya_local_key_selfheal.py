from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "tuya_local_key_selfheal.py"
)
_SPEC = importlib.util.spec_from_file_location("tuya_local_key_selfheal", MODULE_PATH)
assert _SPEC and _SPEC.loader
lk = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lk)

NOW_MS = 1_784_000_000_000

FRESH = {
    "access_token": "a-fresh",
    "refresh_token": "r-fresh",
    "expire_time": 7200,
    "t": NOW_MS - 60_000,
    "uid": "az1",
}
OLDER = {
    "access_token": "a-old",
    "refresh_token": "r-old",
    "expire_time": 7200,
    "t": NOW_MS - 90 * 60 * 1000,
    "uid": "az1",
}
EXPIRED = {
    "access_token": "a",
    "refresh_token": "r",
    "expire_time": 7200,
    "t": NOW_MS - 100 * 3600 * 1000,
    "uid": "az1",
}


def test_token_expiry_ms() -> None:
    assert lk.token_expiry_ms(FRESH) == FRESH["t"] + 7200 * 1000
    assert lk.token_expiry_ms({}) == 0


def test_pick_newer_token_prefers_higher_expiry() -> None:
    assert lk.pick_newer_token(OLDER, FRESH) == FRESH
    assert lk.pick_newer_token(FRESH, OLDER) == FRESH
    assert lk.pick_newer_token(None, FRESH) == FRESH
    assert lk.pick_newer_token(EXPIRED, None) == EXPIRED
    assert lk.pick_newer_token(None, None) is None


def test_load_best_token_prefers_bridge_when_newer(tmp_path: Path) -> None:
    bridge = tmp_path / "runtime.json"
    bridge.write_text(json.dumps(FRESH), encoding="utf-8")
    config = {
        "data": {
            "entries": [
                {
                    "domain": "tuya",
                    "data": {
                        "token_info": OLDER,
                        "user_code": "Ba0osdh",
                        "endpoint": "https://apigw.tuyaus.com",
                    },
                }
            ]
        }
    }
    cfg_path = tmp_path / "core.config_entries"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    best, meta = lk.load_best_token_info(bridge_path=bridge, config_entries_path=cfg_path)
    assert best == FRESH
    assert meta["token_source"] == "bridge_runtime"
    assert meta["user_code"] == "Ba0osdh"


def test_load_best_token_falls_back_to_ha_when_bridge_stale(tmp_path: Path) -> None:
    """Incidente quarto 2026-07-22: bridge 16h morto, HA com token fresco."""
    bridge = tmp_path / "runtime.json"
    bridge.write_text(json.dumps(EXPIRED), encoding="utf-8")
    config = {
        "data": {
            "entries": [
                {
                    "domain": "tuya",
                    "data": {
                        "token_info": FRESH,
                        "user_code": "Ba0osdh",
                        "endpoint": "https://apigw.tuyaus.com",
                    },
                }
            ]
        }
    }
    cfg_path = tmp_path / "core.config_entries"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    best, meta = lk.load_best_token_info(bridge_path=bridge, config_entries_path=cfg_path)
    assert best == FRESH
    assert meta["token_source"] == "ha_config_entries"


def test_read_ha_token_permission_error() -> None:
    class BadPath:
        def read_text(self, encoding: str = "utf-8") -> str:
            raise PermissionError("Permission denied")

        def __str__(self) -> str:
            return "/var/lib/tuya-local-selfheal/ha_token"

    with pytest.raises(PermissionError, match="chown homelab"):
        lk.read_ha_token(BadPath())  # type: ignore[arg-type]


def test_discover_tuya_local_targets(tmp_path: Path) -> None:
    config = {
        "data": {
            "entries": [
                {
                    "entry_id": "E1",
                    "domain": "tuya_local",
                    "disabled_by": None,
                    "data": {"device_id": "dev1", "local_key": "k1"},
                },
                {
                    "entry_id": "E2",
                    "domain": "tuya_local",
                    "disabled_by": "user",
                    "data": {"device_id": "dev2", "local_key": "k2"},
                },
                {
                    "entry_id": "E3",
                    "domain": "tuya",
                    "data": {"token_info": FRESH},
                },
            ]
        }
    }
    cfg = tmp_path / "core.config_entries"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    found = lk.discover_tuya_local_targets(cfg)
    assert found == {"E1": "dev1"}
