from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from tools.trading_guardrails_control import (
    _basic_auth_ok,
    _compute_manual_sell_pnl,
    _ensure_database_url,
    _extract_database_url_from_systemctl,
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
    assert _basic_auth_ok("Basic Z3VhcmRyYWlsczpzZWNyZXQ=", "guardrails", "secret")
    assert not _basic_auth_ok("Basic Z3VhcmRyYWlsczp3cm9uZw==", "guardrails", "secret")
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
        "X-authentik-groups": "Grafana Admins",
    }
    assert _authentik_auth_ok(headers, "Grafana Admins")
    assert not _authentik_auth_ok(headers, "Outra Role")


def test_build_manual_sell_path_encodes_profile() -> None:
    assert build_manual_sell_path("aggressive") == "/manual-sell?profile=aggressive"
    assert build_manual_sell_path("profile teste") == "/manual-sell?profile=profile+teste"


def test_compute_manual_sell_pnl_accounts_for_fees() -> None:
    pnl, pnl_pct = _compute_manual_sell_pnl(avg_entry=70000.0, price=71000.0, size=0.001)
    assert round(pnl, 6) == round((71000 - 70000) * 0.001 - ((71000 + 70000) * 0.001 * 0.001), 6)
    assert pnl_pct > 0


def test_extract_database_url_from_systemctl_output() -> None:
    output = "FOO=bar DATABASE_URL=postgres://user:pass@host/db BAZ=qux"
    assert _extract_database_url_from_systemctl(output) == "postgres://user:pass@host/db"


def test_ensure_database_url_prefers_systemctl_runtime_value(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    fake_result = Mock(stdout="DATABASE_URL=postgres://runtime/db OTHER=value\n")

    with patch("tools.trading_guardrails_control.subprocess.run", return_value=fake_result):
        _ensure_database_url()

    assert os.environ["DATABASE_URL"] == "postgres://runtime/db"


def test_ensure_database_url_falls_back_to_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=postgres://dotenv/db\n", encoding="utf-8")

    with patch("tools.trading_guardrails_control.subprocess.run", side_effect=RuntimeError("no systemctl")):
        with patch("tools.trading_guardrails_control.AGENT_DIR", tmp_path):
            _ensure_database_url()

    assert os.environ["DATABASE_URL"] == "postgres://dotenv/db"
