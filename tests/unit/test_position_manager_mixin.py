"""Testes unitários para PositionManagerMixin."""
from __future__ import annotations

import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "btc_trading_agent"))

from position_manager_mixin import PositionManagerMixin

_FEE = 0.001


# ── Builders ─────────────────────────────────────────────────────────────────

def _entry(price: float, size: float, *, ts: float | None = None, target_sell: float = 0.0) -> dict:
    e: dict = {"price": price, "size": size, "target_sell": target_sell}
    if ts is not None:
        e["ts"] = ts
    return e


def _make_agent(
    *,
    position: float = 0.1,
    entry_price: float = 90_000.0,
    entries: list | None = None,
    dry_run: bool = True,
    live_cfg: dict | None = None,
) -> PositionManagerMixin:
    class _Agent(PositionManagerMixin):
        def __init__(self):
            self._trade_lock = threading.Lock()
            self._trading_fee_pct = _FEE
            self.symbol = "BTC-USDT"
            self.db = MagicMock()
            self.db.record_trade.return_value = 1
            self.state = SimpleNamespace(
                position=position,
                entry_price=entry_price,
                entries=list(entries or []),
                dry_run=dry_run,
                position_count=0,
                raw_entry_count=0,
                logical_position_slots=0,
                last_sell_entry_price=0.0,
                total_pnl=0.0,
                winning_trades=0,
                total_trades=0,
                daily_trades=0,
                last_trade_time=0.0,
                target_sell_price=0.0,
                target_sell_reason="",
                buy_success_pressure=0.0,
                buy_success_factor=1.0,
                buy_dynamic_batch_cap_usdt=0.0,
                dca_valley_low=0.0,
                trailing_high=0.0,
            )

        def _load_live_config(self):
            return live_cfg or {}

        def _current_profile(self):
            return "conservative"

        def _guardrail_allows_slot_sell(self, entry_price, size, current_price, *, bypass_guardrail=False):
            # Guardrail desabilitado no mock padrão; usar live_cfg para ativar.
            cfg = live_cfg or {}
            if not cfg.get("guardrails_active", False) or not cfg.get("guardrails_positive_only_sells", False):
                return True
            if bypass_guardrail:
                return True
            _fee = 0.001
            gross_sell = current_price * size
            if gross_sell <= 0:
                return True
            net = (current_price - entry_price) * size - gross_sell * _fee - entry_price * size * _fee
            min_pct = float(cfg.get("guardrails_min_sell_pnl_pct", 0.003))
            return (net / gross_sell) >= min_pct

    return _Agent()


# ── _sync_position_tracking ──────────────────────────────────────────────────

class TestSyncPositionTracking:

    def test_no_position_resets_slots(self):
        agent = _make_agent(position=0.0, entry_price=0.0, entries=[])
        agent._sync_position_tracking()
        assert agent.state.logical_position_slots == 0

    def test_entries_set_raw_and_logical_count(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001), _entry(88_000, 0.001)]
        agent = _make_agent(position=0.003, entries=entries)
        agent._sync_position_tracking()
        assert agent.state.raw_entry_count == 3
        assert agent.state.logical_position_slots == 3

    def test_legacy_position_without_entries(self):
        # posição aberta (entry_price > 0) mas sem lista de entries → slot = 1
        agent = _make_agent(position=0.1, entry_price=90_000.0, entries=[])
        agent._sync_position_tracking()
        assert agent.state.logical_position_slots == 1


# ── _check_per_slot_exits: max_hold_hours ────────────────────────────────────

class TestMaxHoldHours:

    def test_disabled_when_zero(self):
        old_ts = time.time() - 50 * 3600  # 50h atrás
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(position=0.001, entries=entries, live_cfg={"max_hold_hours": 0})
        sold = agent._check_per_slot_exits(91_000.0)
        assert not sold

    def test_triggers_when_hold_exceeds_limit(self):
        old_ts = time.time() - 25 * 3600  # 25h atrás
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={"max_hold_hours": 24},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert sold

    def test_does_not_trigger_before_limit(self):
        recent_ts = time.time() - 12 * 3600  # 12h atrás
        entries = [_entry(90_000, 0.001, ts=recent_ts)]
        agent = _make_agent(
            position=0.001,
            entries=entries,
            live_cfg={"max_hold_hours": 24},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert not sold

    def test_no_ts_skipped(self):
        # entrada sem timestamp → não tenta saída por tempo
        entries = [_entry(90_000, 0.001)]  # sem ts
        agent = _make_agent(
            position=0.001,
            entries=entries,
            live_cfg={"max_hold_hours": 1},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert not sold


# ── _check_per_slot_exits: trailing stop ─────────────────────────────────────

class TestPerSlotTrailingStop:

    def _cfg(self, activation: float = 0.01, trail: float = 0.005) -> dict:
        return {"trailing_stop": {"enabled": True, "activation_pct": activation, "trail_pct": trail}}

    def test_triggers_when_drop_exceeds_trail(self):
        # slot_high = 91_000, price caiu para 90_500 → drop ≈ 0.55% > trail 0.5%
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 91_000.0
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg()
        )
        sold = agent._check_per_slot_exits(90_500.0)
        assert sold

    def test_no_trigger_below_activation(self):
        # gain de apenas 0.3% < activation 1% → trailing não ativa
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 90_270.0  # +0.3%
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg(activation=0.01)
        )
        sold = agent._check_per_slot_exits(89_900.0)
        assert not sold

    def test_trailing_high_updated(self):
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 90_000.0
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg()
        )
        agent._check_per_slot_exits(91_000.0)  # novo high
        assert agent.state.entries[0]["trailing_high"] == pytest.approx(91_000.0)


# ── _check_per_slot_exits: take profit ───────────────────────────────────────

class TestPerSlotTakeProfit:

    def test_triggers_at_target(self):
        entries = [_entry(90_000, 0.001, target_sell=91_000.0)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        sold = agent._check_per_slot_exits(91_000.0)
        assert sold

    def test_no_trigger_below_target(self):
        entries = [_entry(90_000, 0.001, target_sell=91_000.0)]
        agent = _make_agent(position=0.001, entries=entries)
        sold = agent._check_per_slot_exits(90_900.0)
        assert not sold

    def test_no_trigger_when_target_zero(self):
        entries = [_entry(90_000, 0.001, target_sell=0.0)]
        agent = _make_agent(position=0.001, entries=entries)
        sold = agent._check_per_slot_exits(99_999.0)
        assert not sold


# ── _check_per_slot_exits: stop loss ─────────────────────────────────────────

class TestPerSlotStopLoss:

    def _cfg(self, pct: float = 0.03) -> dict:
        return {"auto_stop_loss": {"enabled": True, "pct": pct}}

    def test_triggers_at_loss(self):
        # preço caiu 3.1% → SL de 3% dispara
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg(0.03)
        )
        sold = agent._check_per_slot_exits(87_210.0)  # -3.1%
        assert sold

    def test_no_trigger_above_threshold(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg(0.03)
        )
        sold = agent._check_per_slot_exits(88_000.0)  # -2.2% (acima do SL)
        assert not sold

    def test_sells_all_slots_that_individually_hit_stop_loss(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001)]
        agent = _make_agent(
            position=0.002,
            entry_price=89_500.0,
            entries=entries,
            live_cfg=self._cfg(0.02),
        )
        sold = agent._check_per_slot_exits(87_000.0)
        assert sold
        assert agent.state.position == 0.0
        assert agent.state.entries == []

    def test_disabled_when_not_enabled(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entries=entries,
            live_cfg={"auto_stop_loss": {"enabled": False, "pct": 0.001}},
        )
        sold = agent._check_per_slot_exits(1.0)  # preço ridículo → sem SL
        assert not sold


# ── _execute_slot_sell ────────────────────────────────────────────────────────

class TestExecuteSlotSell:

    def test_dry_run_no_real_order(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries, dry_run=True)
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is True
        # nenhuma chamada real de order
        from kucoin_api import place_market_order  # noqa: F401 — import check only
        agent.db.record_trade.assert_called_once()

    def test_removes_slot_from_entries(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001)]
        agent = _make_agent(position=0.002, entry_price=89_500.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["price"] == 89_000.0

    def test_recalculates_weighted_entry_price(self):
        entries = [_entry(90_000, 0.001), _entry(88_000, 0.002)]
        agent = _make_agent(position=0.003, entry_price=88_667.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        # apenas slot 88_000 restante → entry_price = 88_000
        assert agent.state.entry_price == pytest.approx(88_000.0, abs=1.0)

    def test_clears_state_when_last_slot_sold(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert agent.state.position == 0.0
        assert agent.state.entry_price == 0.0
        assert agent.state.entries == []
        assert agent.state.target_sell_price == 0.0
        assert agent.state.trailing_high == 0.0

    def test_rebuy_lock_set_to_entry_price(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert agent.state.last_sell_entry_price == pytest.approx(90_000.0)

    def test_pnl_positive_increments_winning_trades(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")  # lucro
        assert agent.state.winning_trades == 1
        assert agent.state.total_trades == 1
        assert agent.state.total_pnl > 0

    def test_pnl_negative_no_winning_trade(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 85_000.0, "STOP_LOSS")  # prejuízo
        assert agent.state.winning_trades == 0
        assert agent.state.total_trades == 1
        assert agent.state.total_pnl < 0

    def test_invalid_entry_idx_returns_false(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entries=entries)
        result = agent._execute_slot_sell(5, 91_000.0, "TEST")
        assert result is False

    def test_zero_size_returns_false(self):
        entries = [{"price": 90_000, "size": 0}]
        agent = _make_agent(position=0.001, entries=entries)
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is False

    def test_no_entries_returns_false(self):
        agent = _make_agent(position=0.0, entries=[])
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is False


class TestExecuteProfitableSlotSells:

    def test_sells_only_profitable_slots(self):
        entries = [_entry(90_000, 0.001), _entry(100_000, 0.001)]
        agent = _make_agent(position=0.002, entry_price=95_000.0, entries=entries, dry_run=True)

        sold = agent._execute_profitable_slot_sells(92_000.0, "MODEL_SELL")

        assert sold == 1
        assert agent.state.position == pytest.approx(0.001)
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["price"] == 100_000

    def test_returns_zero_when_no_profitable_slots(self):
        entries = [_entry(100_000, 0.001), _entry(101_000, 0.001)]
        agent = _make_agent(position=0.002, entry_price=100_500.0, entries=entries, dry_run=True)

        sold = agent._execute_profitable_slot_sells(99_000.0, "MODEL_SELL")

        assert sold == 0
        assert agent.state.position == pytest.approx(0.002)
        assert len(agent.state.entries) == 2


class TestPostSellNotifyWorker:

    def test_telegram_send_is_direct_by_default(self):
        agent = _make_agent()
        ollama_resp = SimpleNamespace(ok=True, json=lambda: {"response": "msg"})
        telegram_resp = SimpleNamespace(ok=True, status_code=200, text="ok")

        with (
            patch("position_manager_mixin.subprocess.run", return_value=SimpleNamespace(returncode=0, stderr=b"")),
            patch("kucoin_api._resolve_telegram_bot_token", return_value="token"),
            patch("kucoin_api._resolve_telegram_chat_id", return_value="chat"),
            patch("requests.post", side_effect=[ollama_resp, telegram_resp]) as post_mock,
            patch.dict("os.environ", {}, clear=False),
        ):
            agent._post_sell_notify_worker(90_000.0, 91_000.0, 0.001, 1.0, 1.1, "TARGET", 0)

        assert post_mock.call_count == 2
        telegram_call = post_mock.call_args_list[1]
        assert "proxies" not in telegram_call.kwargs

    def test_telegram_proxy_failure_retries_direct(self):
        agent = _make_agent()
        ollama_resp = SimpleNamespace(ok=True, json=lambda: {"response": "msg"})
        telegram_resp = SimpleNamespace(ok=True, status_code=200, text="ok")

        def _post_side_effect(url, **kwargs):
            if url.endswith("/api/generate"):
                return ollama_resp
            if kwargs.get("proxies"):
                raise RuntimeError("proxy down")
            return telegram_resp

        with (
            patch("position_manager_mixin.subprocess.run", return_value=SimpleNamespace(returncode=0, stderr=b"")),
            patch("kucoin_api._resolve_telegram_bot_token", return_value="token"),
            patch("kucoin_api._resolve_telegram_chat_id", return_value="chat"),
            patch("requests.post", side_effect=_post_side_effect) as post_mock,
            patch.dict("os.environ", {"TELEGRAM_PROXY_URL": "http://127.0.0.1:3128"}, clear=False),
        ):
            agent._post_sell_notify_worker(90_000.0, 91_000.0, 0.001, 1.0, 1.1, "TARGET", 0)

        assert post_mock.call_count == 3
        proxy_call = post_mock.call_args_list[1]
        direct_call = post_mock.call_args_list[2]
        assert proxy_call.kwargs["proxies"] == {
            "https": "http://127.0.0.1:3128",
            "http": "http://127.0.0.1:3128",
        }
        assert "proxies" not in direct_call.kwargs


# ── _guardrail_allows_slot_sell (RiskGuardianMixin) ──────────────────────────

class TestGuardrailAllowsSlotSell:
    """Testes unitários para RiskGuardianMixin._guardrail_allows_slot_sell."""

    def _make_guardrail_agent(
        self,
        *,
        active: bool = True,
        positive_only: bool = True,
        min_pnl_pct: float = 0.003,
    ):
        from risk_guardian_mixin import RiskGuardianMixin

        class _GuardAgent(RiskGuardianMixin):
            def __init__(self_inner):
                self_inner._trading_fee_pct = _FEE

            def _get_guardrail_sell_protection_cfg(self_inner):
                return {
                    "active": active,
                    "positive_only_sells": positive_only,
                    "min_sell_pnl_pct": min_pnl_pct,
                }

        return _GuardAgent()

    def test_inactive_guardrail_always_allows(self):
        """Guardrail desativado: qualquer venda passa, mesmo com PnL negativo."""
        agent = self._make_guardrail_agent(active=False)
        # slot profundamente no prejuízo
        assert agent._guardrail_allows_slot_sell(90_000.0, 0.001, 80_000.0) is True

    def test_positive_only_false_always_allows(self):
        """positive_only_sells=False desativa a restrição de PnL."""
        agent = self._make_guardrail_agent(active=True, positive_only=False)
        assert agent._guardrail_allows_slot_sell(90_000.0, 0.001, 80_000.0) is True

    def test_blocks_when_pnl_below_threshold(self):
        """Net PnL abaixo do mínimo (0.3%) → venda bloqueada."""
        agent = self._make_guardrail_agent(min_pnl_pct=0.003)
        # entry=90_000, size=0.001, price=90_200 → net_pnl ≈ 0.022% < 0.3%
        assert agent._guardrail_allows_slot_sell(90_000.0, 0.001, 90_200.0) is False

    def test_allows_when_pnl_above_threshold(self):
        """Net PnL acima do mínimo → venda permitida."""
        agent = self._make_guardrail_agent(min_pnl_pct=0.003)
        # entry=90_000, size=0.001, price=90_550 → net_pnl ≈ 0.41% > 0.3%
        assert agent._guardrail_allows_slot_sell(90_000.0, 0.001, 90_550.0) is True

    def test_bypass_true_always_allows_regardless_of_pnl(self):
        """bypass_guardrail=True ignora PnL — saída de proteção de risco."""
        agent = self._make_guardrail_agent(min_pnl_pct=0.05)  # limiar alto
        # slot com perda severa, mas bypass=True → executa
        assert agent._guardrail_allows_slot_sell(
            90_000.0, 0.001, 70_000.0, bypass_guardrail=True
        ) is True

    def test_zero_size_always_allows(self):
        """Tamanho zero → gross_sell=0 → guarda trata como seguro e permite."""
        agent = self._make_guardrail_agent()
        assert agent._guardrail_allows_slot_sell(90_000.0, 0.0, 91_000.0) is True


# ── Integração: _check_per_slot_exits + guardrail ─────────────────────────────

class TestGuardrailPerSlotExitIntegration:
    """Valida que _check_per_slot_exits respeita o guardrail end-to-end.

    Usa live_cfg com guardrails_active=True para que o mock de
    _guardrail_allows_slot_sell (em _Agent) avalie PnL real.
    """

    def _guardrail_cfg(self, min_pnl_pct: float = 0.003) -> dict:
        return {
            "guardrails_active": True,
            "guardrails_positive_only_sells": True,
            "guardrails_min_sell_pnl_pct": min_pnl_pct,
        }

    def test_maxhold_blocks_underwater_slot(self):
        """MaxHold dispara mas guardrail bloqueia slot com PnL negativo."""
        old_ts = time.time() - 25 * 3600  # 25h atrás
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={"max_hold_hours": 24, **self._guardrail_cfg()},
        )
        sold = agent._check_per_slot_exits(88_000.0)  # -2.27% PnL → bloqueado
        assert not sold
        assert agent.state.position == pytest.approx(0.001)
        assert len(agent.state.entries) == 1

    def test_maxhold_allows_profitable_slot(self):
        """MaxHold dispara e guardrail permite slot genuinamente lucrativo."""
        old_ts = time.time() - 25 * 3600
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={"max_hold_hours": 24, **self._guardrail_cfg()},
        )
        sold = agent._check_per_slot_exits(91_000.0)  # +0.91% net PnL → permitido
        assert sold
        assert agent.state.position == pytest.approx(0.0)

    def test_trailing_stop_blocks_underwater_slot(self):
        """TrailingStop dispara mas guardrail bloqueia slot cujo preço ficou abaixo da entrada."""
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 93_000.0  # +3.3% → ativação satisfeita
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={
                "trailing_stop": {"enabled": True, "activation_pct": 0.01, "trail_pct": 0.005},
                **self._guardrail_cfg(),
            },
        )
        # drop from high: (93000-88000)/93000=5.4% > trail 0.5% → dispara
        # PnL at 88_000: net ≈ -2.3% < 0.3% → guardrail bloqueia
        sold = agent._check_per_slot_exits(88_000.0)
        assert not sold
        assert agent.state.position == pytest.approx(0.001)

    def test_stop_loss_bypasses_guardrail_and_executes(self):
        """StopLoss tem bypass_guardrail=True → executa mesmo com PnL negativo."""
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={
                "auto_stop_loss": {"enabled": True, "pct": 0.03},
                **self._guardrail_cfg(),
            },
        )
        # preço caiu 4% → SL dispara (3% threshold); bypass=True → guardrail ignorado
        sold = agent._check_per_slot_exits(86_400.0)
        assert sold
        assert agent.state.position == pytest.approx(0.0)


# ── Herança dos mixins em BitcoinTradingAgent ─────────────────────────────────

class TestMixinInheritance:

    def test_mixin_methods_present_in_mro(self):
        from sell_target_mixin import SellTargetMixin
        from risk_guardian_mixin import RiskGuardianMixin
        from position_manager_mixin import PositionManagerMixin

        expected_methods = [
            # SellTargetMixin
            "_sync_target_sell_with_ai",
            "_serialize_target_sell_metadata",
            "_build_trade_metadata",
            "_stamp_latest_open_buy_target",
            # RiskGuardianMixin
            "_get_guardrail_sell_protection_cfg",
            "_estimate_sell_outcome",
            "_should_allow_low_net_profit_sell",
            # PositionManagerMixin
            "_sync_position_tracking",
            "_check_per_slot_exits",
            "_execute_slot_sell",
            "_execute_profitable_slot_sells",
        ]

        all_mixin_attrs: set[str] = set()
        for mixin in (SellTargetMixin, RiskGuardianMixin, PositionManagerMixin):
            all_mixin_attrs.update(
                name for name in dir(mixin) if not name.startswith("__")
            )

        for method in expected_methods:
            assert method in all_mixin_attrs, f"Método ausente nos mixins: {method}"
