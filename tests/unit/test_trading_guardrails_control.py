from __future__ import annotations

import base64
import json
from pathlib import Path

from tools.trading_guardrails_control import (
    _basic_auth_ok,
    _compute_manual_sell_pnl,
    _authentik_auth_ok,
    build_manual_sell_path,
    build_handler,
    load_status,
    reactivate_guardrails,
)


def _write_config(path: Path, *, max_daily_trades: int, max_daily_loss: float, dry_run: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "dry_run": dry_run,
                "max_daily_trades": max_daily_trades,
                "max_daily_loss": max_daily_loss,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_reactivate_guardrails_restores_expected_caps(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)

    statuses = reactivate_guardrails(tmp_path)

    values = {item.profile: item for item in statuses}
    assert values["aggressive"].max_daily_trades == 9999
    assert values["aggressive"].max_daily_loss == 0.03
    assert values["conservative"].max_daily_trades == 9999
    assert values["conservative"].max_daily_loss == 0.085


def test_load_status_reads_live_values(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=111, max_daily_loss=1.5, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=222, max_daily_loss=2.5, dry_run=True)

    statuses = {item.profile: item for item in load_status(tmp_path)}

    assert statuses["aggressive"].max_daily_trades == 111
    assert statuses["aggressive"].max_daily_loss == 1.5
    assert statuses["conservative"].max_daily_trades == 222
    assert statuses["conservative"].dry_run is True


def test_basic_auth_validation() -> None:
    valid = "Basic " + base64.b64encode(b"guardrails:not-real").decode("ascii")
    invalid = "Basic " + base64.b64encode(b"guardrails:wrong-value").decode("ascii")

    assert _basic_auth_ok(valid, "guardrails", "not-real")
    assert not _basic_auth_ok(invalid, "guardrails", "not-real")
    assert not _basic_auth_ok(None, "guardrails", "secret")


def test_handler_supports_get_reactivate(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)
    handler = build_handler(tmp_path, "guardrails", "secret")
    assert hasattr(handler, "do_GET")


def test_handler_allows_authentik_fronted_mode_without_password(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=9999, max_daily_loss=999999, dry_run=False)
    handler = build_handler(tmp_path, "guardrails", None)
    assert hasattr(handler, "do_POST")


def test_authentik_group_validation() -> None:
    headers = {
        "X-authentik-username": "edenilson",
        "X-authentik-groups": "Grafana Admins, Trading Guardrails Operators",
    }
    assert _authentik_auth_ok(headers, "Trading Guardrails Operators")
    assert not _authentik_auth_ok(headers, "Outra Role")


def test_build_manual_sell_path_encodes_profile() -> None:
    assert build_manual_sell_path("aggressive") == "/manual-sell?profile=aggressive"
    assert build_manual_sell_path("profile teste") == "/manual-sell?profile=profile+teste"


def test_compute_manual_sell_pnl_accounts_for_fees() -> None:
    pnl, pnl_pct = _compute_manual_sell_pnl(avg_entry=70000.0, price=71000.0, size=0.001)
    assert round(pnl, 6) == round((71000 - 70000) * 0.001 - ((71000 + 70000) * 0.001 * 0.001), 6)
    assert pnl_pct > 0
