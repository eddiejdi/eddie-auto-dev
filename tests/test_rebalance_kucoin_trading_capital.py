"""Testes unitários para rebalance_kucoin_trading_capital — build_plan() e main()."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("kucoin_api", MagicMock())

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import rebalance_kucoin_trading_capital as rebalance  # noqa: E402


def _set_balances(monkeypatch, master_usdt, subs_usdt):
    """subs_usdt: dict sub_name -> saldo USDT disponível na conta trade."""
    def fake_get_balances(account_type="trade"):
        assert account_type == "trade"
        return [{"currency": "USDT", "available": master_usdt}]

    def fake_get_sub_account_balances():
        return [
            {"sub_name": name, "account_type": "trade", "currency": "USDT", "available": avail}
            for name, avail in subs_usdt.items()
        ]

    monkeypatch.setattr(rebalance.k, "get_balances", fake_get_balances)
    monkeypatch.setattr(rebalance.k, "get_sub_account_balances", fake_get_sub_account_balances)


class TestBuildPlanTopUp:
    def test_prioritizes_lowest_sub_when_budget_insufficient(self, monkeypatch):
        """Master só tem orçamento pra uma subconta — deve escolher a mais baixa.

        BTCConservative/ETHConservative ficam exatamente na meta (sem excedente),
        pra não disparar sweep e inflar o orçamento no meio do teste.
        """
        _set_balances(
            monkeypatch,
            master_usdt=rebalance.MASTER_MIN_RESERVE_USDT + 6.0,  # orçamento = 6.0
            subs_usdt={
                "BTCAgressive": 23.07,   # mais baixa
                "ETHAgressive": 23.45,
                "BTCConservative": rebalance.TARGET_SUB_USDT,
                "ETHConservative": rebalance.TARGET_SUB_USDT,
            },
        )

        plans = rebalance.build_plan()
        out_plans = [p for p in plans if p.direction == "OUT"]

        assert len(out_plans) == 1
        assert out_plans[0].sub_name == "BTCAgressive"
        assert out_plans[0].amount == pytest.approx(6.0)

    def test_never_drains_master_below_reserve(self, monkeypatch):
        """Nenhum plano deve deixar o master abaixo de MASTER_MIN_RESERVE_USDT."""
        master_usdt = rebalance.MASTER_MIN_RESERVE_USDT + 3.0
        _set_balances(
            monkeypatch,
            master_usdt=master_usdt,
            subs_usdt={"BTCAgressive": 20.0, "ETHAgressive": 20.0},
        )

        plans = rebalance.build_plan()
        total_out = sum(p.amount for p in plans if p.direction == "OUT")

        assert master_usdt - total_out >= rebalance.MASTER_MIN_RESERVE_USDT

    def test_respects_max_transfer_per_run(self, monkeypatch):
        """Mesmo com master rico, o total de OUT não passa do teto por execução."""
        _set_balances(
            monkeypatch,
            master_usdt=1000.0,
            subs_usdt={
                "BTCAgressive": 1.0,
                "ETHAgressive": 1.0,
                "BTCConservative": 1.0,
                "ETHConservative": 1.0,
            },
        )

        plans = rebalance.build_plan()
        total_out = sum(p.amount for p in plans if p.direction == "OUT")

        assert total_out <= rebalance.MAX_TRANSFER_TOTAL_PER_RUN_USDT

    def test_no_topup_when_all_subs_above_minimum(self, monkeypatch):
        _set_balances(
            monkeypatch,
            master_usdt=100.0,
            subs_usdt={"BTCAgressive": 30.0, "ETHAgressive": 30.0},
        )

        plans = rebalance.build_plan()

        assert not [p for p in plans if p.direction == "OUT"]


class TestBuildPlanSweep:
    def test_sweeps_excess_above_target_to_master(self, monkeypatch):
        _set_balances(
            monkeypatch,
            master_usdt=50.0,
            subs_usdt={"BTCConservative": 40.0, "ETHConservative": 30.0},
        )

        plans = rebalance.build_plan()
        in_plans = {p.sub_name: p.amount for p in plans if p.direction == "IN"}

        assert in_plans["BTCConservative"] == pytest.approx(40.0 - rebalance.TARGET_SUB_USDT)
        assert "ETHConservative" not in in_plans  # exatamente na meta, sem excedente


class TestMainExecute:
    def test_execute_calls_sub_transfer_with_expected_args(self, monkeypatch, capsys):
        _set_balances(
            monkeypatch,
            master_usdt=rebalance.MASTER_MIN_RESERVE_USDT + 10.0,
            subs_usdt={"BTCAgressive": 20.0, "ETHAgressive": 30.0},
        )
        calls = []

        def fake_sub_transfer(currency, amount, sub_user_id, direction, account_type, sub_account_type):
            calls.append(dict(
                currency=currency, amount=amount, sub_user_id=sub_user_id,
                direction=direction, account_type=account_type, sub_account_type=sub_account_type,
            ))
            return {"success": True, "orderId": "fake-order"}

        monkeypatch.setattr(rebalance.k, "sub_transfer", fake_sub_transfer)
        monkeypatch.setattr(sys, "argv", ["rebalance_kucoin_trading_capital.py", "--execute"])

        exit_code = rebalance.main()

        assert exit_code == 0
        assert len(calls) == 1
        assert calls[0]["currency"] == "USDT"
        assert calls[0]["direction"] == "OUT"
        assert calls[0]["sub_user_id"] == rebalance.SUB_USER_IDS["BTCAgressive"]
        assert calls[0]["account_type"] == "TRADE"
        assert calls[0]["sub_account_type"] == "TRADE"

    def test_execute_stops_on_first_failure(self, monkeypatch):
        _set_balances(
            monkeypatch,
            master_usdt=1000.0,
            subs_usdt={"BTCAgressive": 1.0, "ETHAgressive": 1.0},
        )
        calls = []

        def failing_sub_transfer(currency, amount, sub_user_id, direction, account_type, sub_account_type):
            calls.append(sub_user_id)
            return {"success": False, "error": "boom"}

        monkeypatch.setattr(rebalance.k, "sub_transfer", failing_sub_transfer)
        monkeypatch.setattr(sys, "argv", ["rebalance_kucoin_trading_capital.py", "--execute"])

        exit_code = rebalance.main()

        assert exit_code == 1
        assert len(calls) == 1  # abortou após a primeira falha, não seguiu pras próximas

    def test_dry_run_does_not_call_sub_transfer(self, monkeypatch):
        _set_balances(
            monkeypatch,
            master_usdt=rebalance.MASTER_MIN_RESERVE_USDT + 10.0,
            subs_usdt={"BTCAgressive": 20.0},
        )
        mock_sub_transfer = MagicMock()
        monkeypatch.setattr(rebalance.k, "sub_transfer", mock_sub_transfer)
        monkeypatch.setattr(sys, "argv", ["rebalance_kucoin_trading_capital.py"])

        exit_code = rebalance.main()

        assert exit_code == 0
        mock_sub_transfer.assert_not_called()
