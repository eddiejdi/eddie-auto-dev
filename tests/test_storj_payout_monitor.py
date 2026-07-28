from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "storj_payout_monitor.py"
)
_SPEC = importlib.util.spec_from_file_location("storj_payout_monitor", MODULE_PATH)
assert _SPEC and _SPEC.loader
spm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(spm)


HELD_HISTORY = [
    {"satelliteID": "sat1", "totalDisposed": 10319, "totalHeld": 10319},
    {"satelliteID": "sat2", "totalDisposed": 17639, "totalHeld": 17639},
    {"satelliteID": "sat3", "totalDisposed": 392246, "totalHeld": 392246},
    {"satelliteID": "sat4", "totalDisposed": 85483, "totalHeld": 85483},
]

WALLET_BALANCE_RESPONSE = {
    "balances": {
        "0xA0806DA7835a4E63dB2CE44A2b622eF8b73B5DB5": {
            "balance": "531467164",
            "token": {"symbol": "STORJ", "decimals": 8, "usdPrice": 0.061247},
        }
    }
}


def test_fetch_disposed_total_sums_all_satellites():
    with patch.object(spm, "_http_json", return_value=HELD_HISTORY):
        total = spm.fetch_disposed_total()
    assert total == pytest.approx((10319 + 17639 + 392246 + 85483) / 100.0)


def test_fetch_wallet_storj_balance_finds_storj_token():
    with patch.object(spm, "_http_json", return_value=WALLET_BALANCE_RESPONSE):
        balance = spm.fetch_wallet_storj_balance("0xdead")
    assert balance == pytest.approx(531467164 / 1e8)


def test_fetch_wallet_storj_balance_missing_token_returns_zero():
    with patch.object(spm, "_http_json", return_value={"balances": {}}):
        balance = spm.fetch_wallet_storj_balance("0xdead")
    assert balance == 0.0


def test_main_alerts_only_once_per_crossing(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    prom_file = tmp_path / "metrics.prom"
    monkeypatch.setattr(spm, "STATE_FILE", state_file)
    monkeypatch.setattr(spm, "PROM_FILE", prom_file)
    monkeypatch.setattr(spm, "ALERT_THRESHOLD_USD", 20.0)

    alerts = []
    monkeypatch.setattr(spm, "send_telegram_alert", lambda msg: alerts.append(msg))
    monkeypatch.setattr(spm, "fetch_storj_usd_price", lambda: 0.061247)
    monkeypatch.setattr(spm, "fetch_disposed_total", lambda: 100.0)
    monkeypatch.setattr(spm, "fetch_wallet_storj_balance", lambda: 5.31)

    # 1ª execução: sem estado anterior, delta = 0 (last=current) -> sem alerta
    rc = spm.main()
    assert rc == 0
    assert alerts == []
    state = json.loads(state_file.read_text())
    assert state["last_disposed_total"] == 100.0

    # 2ª execução: disposed subiu $25 (>= threshold $20) -> alerta 1x
    monkeypatch.setattr(spm, "fetch_disposed_total", lambda: 125.0)
    rc = spm.main()
    assert rc == 0
    assert len(alerts) == 1
    assert "+$25.00" in alerts[0]

    # 3ª execução: sem novo delta -> nenhum alerta novo
    rc = spm.main()
    assert rc == 0
    assert len(alerts) == 1


def test_main_no_alert_below_threshold(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    prom_file = tmp_path / "metrics.prom"
    monkeypatch.setattr(spm, "STATE_FILE", state_file)
    monkeypatch.setattr(spm, "PROM_FILE", prom_file)
    monkeypatch.setattr(spm, "ALERT_THRESHOLD_USD", 20.0)

    alerts = []
    monkeypatch.setattr(spm, "send_telegram_alert", lambda msg: alerts.append(msg))
    monkeypatch.setattr(spm, "fetch_disposed_total", lambda: 50.0)
    monkeypatch.setattr(spm, "fetch_wallet_storj_balance", lambda: 1.0)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"last_disposed_total": 45.0, "alert_sent_total": 0}))

    rc = spm.main()
    assert rc == 0
    assert alerts == []  # delta = $5, abaixo do threshold $20


def test_main_handles_disposed_fetch_failure(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    prom_file = tmp_path / "metrics.prom"
    monkeypatch.setattr(spm, "STATE_FILE", state_file)
    monkeypatch.setattr(spm, "PROM_FILE", prom_file)

    def _raise():
        raise ValueError("boom")

    monkeypatch.setattr(spm, "fetch_disposed_total", lambda: _raise())
    rc = spm.main()
    assert rc == 2
