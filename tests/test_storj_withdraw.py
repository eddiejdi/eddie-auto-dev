from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "storj_withdraw.py"
)
_SPEC = importlib.util.spec_from_file_location("storj_withdraw", MODULE_PATH)
assert _SPEC and _SPEC.loader
sw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sw)


WALLET_BALANCE_RESPONSE = {
    "balances": {
        "0xA0806DA7835a4E63dB2CE44A2b622eF8b73B5DB5": {
            "balance": "531467164",
            "token": {"symbol": "STORJ", "decimals": 8},
        }
    }
}


def test_fetch_wallet_storj_balance():
    with patch.object(sw, "_http_json", return_value=WALLET_BALANCE_RESPONSE):
        balance = sw.fetch_wallet_storj_balance()
    assert balance == pytest.approx(531467164 / 1e8)


def test_fetch_wallet_storj_balance_zero_when_absent():
    with patch.object(sw, "_http_json", return_value={"balances": {}}):
        balance = sw.fetch_wallet_storj_balance()
    assert balance == 0.0


class _FakeKucoinApiExisting:
    @staticmethod
    def get_deposit_addresses(currency, chain=None):
        assert currency == "STORJ"
        return {
            "success": True,
            "addresses": [{"address": "0xkucoindeposit", "chain": chain}],
        }

    @staticmethod
    def create_deposit_address(currency, chain=None):
        raise AssertionError("não deveria criar se já existe endereço")


class _FakeKucoinApiMissing:
    @staticmethod
    def get_deposit_addresses(currency, chain=None):
        return {"success": True, "addresses": []}

    @staticmethod
    def create_deposit_address(currency, chain=None):
        return {"success": True, "address": "0xnewaddress", "chain": chain}


def test_fetch_kucoin_deposit_address_reuses_existing(monkeypatch):
    monkeypatch.setitem(sys.modules, "kucoin_api", _FakeKucoinApiExisting)
    result = sw.fetch_kucoin_deposit_address(chain="erc20")
    assert result["success"] is True
    assert result["address"] == "0xkucoindeposit"


def test_fetch_kucoin_deposit_address_creates_when_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "kucoin_api", _FakeKucoinApiMissing)
    result = sw.fetch_kucoin_deposit_address(chain="erc20")
    assert result["success"] is True
    assert result["address"] == "0xnewaddress"


def test_main_dry_run_default_does_not_raise(monkeypatch, capsys):
    monkeypatch.setattr(sw, "fetch_wallet_storj_balance", lambda: 5.31)
    monkeypatch.setattr(
        sw, "fetch_kucoin_deposit_address", lambda chain=None: {"success": True, "address": "0xdeposit"}
    )
    monkeypatch.setattr(sys, "argv", ["storj_withdraw.py"])
    rc = sw.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "PLANO DE TRANSFERÊNCIA" in out
    assert "0xdeposit" in out


def test_main_without_present_flag_never_imports_hardware_wallet_libs(monkeypatch, capsys):
    """Garante que o caminho default (sem --i-am-present) não levanta NotImplementedError."""
    monkeypatch.setattr(sw, "fetch_wallet_storj_balance", lambda: 5.31)
    monkeypatch.setattr(
        sw, "fetch_kucoin_deposit_address", lambda chain=None: {"success": True, "address": "0xdeposit"}
    )
    monkeypatch.setattr(sys, "argv", ["storj_withdraw.py"])
    rc = sw.main()
    assert rc == 0


def test_main_with_present_flag_raises_not_implemented(monkeypatch):
    monkeypatch.setattr(sw, "fetch_wallet_storj_balance", lambda: 5.31)
    monkeypatch.setattr(
        sw, "fetch_kucoin_deposit_address", lambda chain=None: {"success": True, "address": "0xdeposit"}
    )
    monkeypatch.setattr(sys, "argv", ["storj_withdraw.py", "--i-am-present"])
    with pytest.raises(NotImplementedError):
        sw.main()


def test_main_handles_balance_fetch_failure(monkeypatch):
    def _raise():
        raise ValueError("boom")

    monkeypatch.setattr(sw, "fetch_wallet_storj_balance", lambda: _raise())
    monkeypatch.setattr(sys, "argv", ["storj_withdraw.py"])
    rc = sw.main()
    assert rc == 2
