from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from tools.trading_guardrails_control import (
    _basic_auth_ok,
    _caps_form_body,
    _compute_manual_sell_pnl,
    _ensure_database_url,
    _extract_database_url_from_systemctl,
    _authentik_auth_ok,
    build_manual_sell_path,
    build_handler,
    CAPS_OPTIONS,
    CAPS_EDITABLE,
    deactivate_guardrails,
    load_status,
    reactivate_guardrails,
    update_profile_caps,
)


def _write_config(
    path: Path,
    *,
    max_daily_trades: int,
    max_daily_loss: float,
    dry_run: bool,
    guardrails_min_sell_pnl_pct: float = 0.025,
    guardrails_positive_only_sells: bool = True,
) -> None:
    path.write_text(
        json.dumps(
            {
                "dry_run": dry_run,
                "guardrails_active": True,
                "max_daily_trades": max_daily_trades,
                "max_daily_loss": max_daily_loss,
                "guardrails_min_sell_pnl_pct": guardrails_min_sell_pnl_pct,
                "guardrails_positive_only_sells": guardrails_positive_only_sells,
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
    assert values["aggressive"].guardrails_active is True
    assert values["conservative"].max_daily_trades == 9999
    assert values["conservative"].max_daily_loss == 0.085
    assert values["conservative"].guardrails_active is True


def test_deactivate_guardrails_disables_flag_without_changing_caps(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=111, max_daily_loss=1.5, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=222, max_daily_loss=2.5, dry_run=True)

    statuses = deactivate_guardrails(tmp_path)

    values = {item.profile: item for item in statuses}
    assert values["aggressive"].guardrails_active is False
    assert values["conservative"].guardrails_active is False
    assert values["aggressive"].max_daily_trades == 111
    assert values["conservative"].max_daily_trades == 222


def test_load_status_reads_live_values(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=111, max_daily_loss=1.5, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=222, max_daily_loss=2.5, dry_run=True)

    statuses = {item.profile: item for item in load_status(tmp_path)}

    assert statuses["aggressive"].max_daily_trades == 111
    assert statuses["aggressive"].max_daily_loss == 1.5
    assert statuses["aggressive"].guardrails_active is True
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


# --- testes update_profile_caps ---

def test_update_profile_caps_changes_specified_values(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=9999, max_daily_loss=0.03, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=9999, max_daily_loss=0.085, dry_run=False)

    statuses = update_profile_caps(
        tmp_path,
        {
            "aggressive": {"max_daily_trades": 5, "max_daily_loss": 0.02},
            "conservative": {"max_daily_trades": 3, "guardrails_min_sell_pnl_pct": 0.01},
        },
    )

    values = {s.profile: s for s in statuses}
    assert values["aggressive"].max_daily_trades == 5
    assert values["aggressive"].max_daily_loss == 0.02
    assert values["conservative"].max_daily_trades == 3
    # verifica que o valor foi gravado no arquivo
    import json as _json
    cons_cfg = _json.loads((tmp_path / "config_BTC_USDT_conservative.json").read_text())
    assert cons_cfg["guardrails_min_sell_pnl_pct"] == 0.01


def test_update_profile_caps_preserves_untouched_keys(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=10, max_daily_loss=0.05, dry_run=True)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=2, max_daily_loss=0.04, dry_run=False)

    update_profile_caps(tmp_path, {"aggressive": {"max_daily_trades": 20}})

    import json as _json
    agg_cfg = _json.loads((tmp_path / "config_BTC_USDT_aggressive.json").read_text())
    assert agg_cfg["dry_run"] is True        # não foi tocado
    assert agg_cfg["max_daily_loss"] == 0.05  # não foi tocado
    assert agg_cfg["max_daily_trades"] == 20   # foi atualizado


def test_caps_options_have_valid_default_values() -> None:
    """Verifica que os valores DEFAULT_TARGETS estão presentes nas opções dos selectboxes."""
    from tools.trading_guardrails_control import DEFAULT_TARGETS
    assert DEFAULT_TARGETS["aggressive"]["max_daily_trades"] in CAPS_OPTIONS["max_daily_trades"]
    assert DEFAULT_TARGETS["aggressive"]["max_daily_loss"] in CAPS_OPTIONS["max_daily_loss"]
    assert DEFAULT_TARGETS["conservative"]["max_daily_trades"] in CAPS_OPTIONS["max_daily_trades"]
    assert DEFAULT_TARGETS["conservative"]["max_daily_loss"] in CAPS_OPTIONS["max_daily_loss"]


def test_caps_editable_keys_exist_in_caps_options() -> None:
    for key, _label, _typ in CAPS_EDITABLE:
        assert key in CAPS_OPTIONS, f"CAPS_OPTIONS está faltando a chave: {key}"
        assert len(CAPS_OPTIONS[key]) > 0


def test_caps_form_body_contains_all_profiles_and_fields(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=5, max_daily_loss=0.03, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=3, max_daily_loss=0.085, dry_run=False)

    body = _caps_form_body(tmp_path)

    assert "aggressive" in body
    assert "conservative" in body
    assert "aggressive_max_daily_trades" in body
    assert "conservative_guardrails_min_sell_pnl_pct" in body
    assert "Aplicar e Reiniciar Agents" in body
    assert "action='/caps'" in body


def test_caps_form_body_marks_current_value_as_selected(tmp_path: Path) -> None:
    _write_config(tmp_path / "config_BTC_USDT_aggressive.json", max_daily_trades=5, max_daily_loss=0.03, dry_run=False)
    _write_config(tmp_path / "config_BTC_USDT_conservative.json", max_daily_trades=3, max_daily_loss=0.085, dry_run=False)

    body = _caps_form_body(tmp_path)

    # O option do valor atual deve estar marcado como selected
    assert "<option value='5' selected>" in body or "value='5' selected" in body


# --- teste dashboard tem botão Ajustar Caps ---

def test_grafana_panel_55_has_caps_button() -> None:
    import json as _json
    from pathlib import Path as _Path
    dash_path = _Path(__file__).resolve().parent.parent.parent / "grafana" / "btc_trading_dashboard_v3_prometheus.json"
    if not dash_path.exists():
        return  # skip se arquivo não existe no ambiente
    dashboard = _json.loads(dash_path.read_text())
    panels = dashboard.get("panels", [])
    panel55 = next((p for p in panels if p.get("id") == 55), None)
    assert panel55 is not None
    content = panel55.get("options", {}).get("content", "")
    assert "guardrails/caps" in content
    assert "Ajustar Caps" in content
