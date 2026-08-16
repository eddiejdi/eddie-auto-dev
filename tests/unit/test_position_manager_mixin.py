"""Testes unitários para PositionManagerMixin."""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

# ====================== SETUP: antes do import dos módulos ======================
# Configura env vars para que _load_credentials() não tente o secrets-agent
# e não envie alertas Telegram. O módulo deve carregar com credenciais vazias.
os.environ.setdefault("KUCOIN_API_KEY", "test_key_abc123")
os.environ.setdefault("KUCOIN_API_SECRET", "test_secret_xyz789")
os.environ.setdefault("KUCOIN_API_PASSPHRASE", "x")
os.environ.setdefault("SECRETS_AGENT_API_KEY", "")  # desativa tentativa ao secrets-agent

# No runner self-hosted o path de produção (/apps/crypto-trader/trading/...)
# vaza no sys.path e o import normal de position_manager_mixin carrega o
# runtime legado. Carregamos os módulos POR ARQUIVO do checkout.
_BTC_AGENT_DIR = (Path(__file__).resolve().parents[2] / "btc_trading_agent").resolve()
assert _BTC_AGENT_DIR.is_dir(), f"btc_trading_agent ausente: {_BTC_AGENT_DIR}"

# Remove path de produção e qualquer entrada residual dos módulos
sys.path[:] = [
    str(_BTC_AGENT_DIR),
    *[
        p
        for p in sys.path
        if "crypto-trader" not in str(p).replace("\\", "/")
        and str(Path(p).resolve()) != str(_BTC_AGENT_DIR)
    ],
]
for _mod in list(sys.modules):
    if _mod in {
        "kucoin_api",
        "secrets_helper",
        "position_manager_mixin",
        "slot_exit_policy",
        "trading_agent",
    } or _mod.startswith("btc_trading_agent"):
        sys.modules.pop(_mod, None)


def _load_checkout_module(name: str) -> ModuleType:
    """Importa um .py do checkout por caminho absoluto (ignora sys.path)."""
    path = _BTC_AGENT_DIR / f"{name}.py"
    assert path.is_file(), f"módulo ausente no checkout: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub secrets_helper no sys.modules antes de carregar kucoin_api (evita
# secrets-agent / path de produção durante o import).
_secrets_stub = ModuleType("secrets_helper")
_secrets_stub.get_secret = lambda *a, **k: None  # type: ignore[attr-defined]
_secrets_stub.get_kucoin_credentials_with_source = (  # type: ignore[attr-defined]
    lambda *a, **k: (
        os.environ.get("KUCOIN_API_KEY", ""),
        os.environ.get("KUCOIN_API_SECRET", ""),
        os.environ.get("KUCOIN_API_PASSPHRASE", ""),
        "env",
    )
)
_secrets_stub.clear_secret_cache = lambda: None  # type: ignore[attr-defined]
sys.modules["secrets_helper"] = _secrets_stub

# Importar com mock de I/O (Telegram) e carregar módulos do checkout por arquivo
with patch("requests.post"):
    # Dependências primeiro (position_manager_mixin importa kucoin_api / slot_exit_policy)
    kucoin_api = _load_checkout_module("kucoin_api")
    _load_checkout_module("slot_exit_policy")
    position_manager_mixin = _load_checkout_module("position_manager_mixin")
    PositionManagerMixin = position_manager_mixin.PositionManagerMixin

_loaded = Path(position_manager_mixin.__file__).resolve()
assert _loaded.parent == _BTC_AGENT_DIR, (
    f"position_manager_mixin carregado de {_loaded}, esperado sob {_BTC_AGENT_DIR}."
)

# Unit tests never hit the live exchange. The self-hosted runner has real
# KuCoin credentials in the ambient env; if a mock is missed, the code used to
# call the API, get 401, return 0, and fail assertions opaquely. Fail loud.
_original_signed_request = getattr(kucoin_api, "_signed_request", None)


def _block_live_kucoin(*_args, **_kwargs):
    raise AssertionError(
        "live KuCoin HTTP blocked in unit tests — mock get_balance / "
        "get_sub_account_balances (got a call to _signed_request)"
    )


if _original_signed_request is not None:
    kucoin_api._signed_request = _block_live_kucoin  # type: ignore[assignment]

_FEE = 0.001


def _subaccount_balance_patches(items):
    """Context managers: subconta + fallback get_balance (runtime legado)."""
    available_sum = sum(float(i.get("available", 0) or 0) for i in items)
    return [
        patch.object(kucoin_api, "get_sub_account_balances", return_value=items),
        patch.object(kucoin_api, "get_balance", return_value=available_sum),
    ]


# ── Builders ─────────────────────────────────────────────────────────────────

def _entry(price: float, size: float, *, ts: float | None = None, target_sell: float = 0.0, trailing_high: float = 0.0) -> dict:
    e: dict = {"price": price, "size": size, "target_sell": target_sell, "trailing_high": trailing_high or price}
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

    def test_untracked_exchange_qty_raises_logical_slots(self):
        entries = [_entry(65_000, 0.00023)]
        agent = _make_agent(position=0.00269, entries=entries)
        agent._sync_position_tracking()
        assert agent.state.raw_entry_count == 1
        assert agent.state.logical_position_slots >= 11


class TestAlignPositionToExchange:

    def test_dry_run_does_not_touch_exchange(self):
        agent = _make_agent(position=0.001, dry_run=True, entries=[_entry(65_000, 0.001)])
        agent._align_position_to_exchange(65_000.0)
        assert agent.state.position == pytest.approx(0.001)

    def test_live_copies_subaccount_base_without_selling(self):
        agent = _make_agent(
            position=0.00023,
            dry_run=False,
            entries=[_entry(65_000, 0.00023)],
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )
        rows = [
            {
                "sub_name": "BTCConservative",
                "account_type": "trade",
                "currency": "BTC",
                "available": 0.000458,
            },
            {
                "sub_name": "BTCConservative",
                "account_type": "trade",
                "currency": "USDT",
                "available": 15.71,
            },
        ]
        with ExitStack() as stack:
            for ctx in _subaccount_balance_patches(rows):
                stack.enter_context(ctx)
            agent._align_position_to_exchange(63_764.0)
        assert agent.state.position == pytest.approx(0.000458)
        assert agent.state.logical_position_slots == 2
        agent.db.record_trade.assert_not_called()


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

    def _cfg(self, pct: float = 0.0, min_profit_pct: float = 0.005) -> dict:
        return {"auto_stop_loss": {"enabled": True, "pct": pct, "min_profit_pct": min_profit_pct}}

    def test_no_trigger_at_loss(self):
        # Nova lógica: SL NÃO dispara com prejuízo
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg(0.03)
        )
        sold = agent._check_per_slot_exits(87_210.0)  # -3.1%
        assert not sold  # Não vende com prejuízo

    def test_no_trigger_below_min_profit(self):
        # Não ativa se lucro < min_profit_pct (0.5%)
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg(0.0, 0.005)
        )
        sold = agent._check_per_slot_exits(90_400.0)  # +0.44% (abaixo de 0.5%)
        assert not sold

    def test_triggers_after_profit(self):
        # Ativa quando lucro >= min_profit_pct e cai do pico
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 91_000.0  # Pico já definido
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg(0.0, 0.005)
        )
        # Preço cai para 90_500 (+0.56%) - ainda lucro, mas caiu do pico (1% trail)
        # stop_price = 91_000 * 0.99 = 90_090
        sold = agent._check_per_slot_exits(90_500.0)
        assert sold  # Vende com lucro

    def test_sells_all_slots_that_individually_hit_stop_loss(self):
        entries = [
            _entry(90_000, 0.001, trailing_high=91_000.0),
            _entry(89_000, 0.001, trailing_high=90_000.0),
        ]
        agent = _make_agent(
            position=0.002,
            entry_price=89_500.0,
            entries=entries,
            live_cfg=self._cfg(0.0, 0.005),
        )
        # Preço cai para 90_000 - ainda lucro para ambos slots
        sold = agent._check_per_slot_exits(90_000.0)
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
            patch("kucoin_api._resolve_telegram_thread_id", return_value="", create=True),
            patch("kucoin_api._get_extra_telegram_chat_ids", return_value=[], create=True),
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
            patch("kucoin_api._resolve_telegram_thread_id", return_value="", create=True),
            patch("kucoin_api._get_extra_telegram_chat_ids", return_value=[], create=True),
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

    def test_stop_loss_bypasses_guardrail_after_profit(self):
        """StopLoss bypass_guardrail=True SOMENTE após lucro mínimo."""
        entries = [_entry(90_000, 0.001, trailing_high=91_000.0)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={
                "auto_stop_loss": {"enabled": True, "pct": 0.0, "min_profit_pct": 0.005},
                **self._guardrail_cfg(),
            },
        )
        # Preço cai para 90_500 (+0.56%) - ainda lucro, mas caiu do pico
        sold = agent._check_per_slot_exits(90_500.0)  # +0.56%
        assert sold  # Vende com lucro, bypassando guardrail
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


# ── _reconcile_position_with_exchange ──────────────────────────────────────

class TestReconcilePositionWithExchange:
    """Cobre reconciliação nas duas direções.

    1. Direção reversa em conta *compartilhada* não cria entries sintéticas
       (risco de atribuir saldo de outro profile) — só alerta.
    2. Direção reversa em saldo *exclusivo* (subconta / kucoin/sub-*) é
       efetiva: ajusta o lote ou grava BUY reconciliado.
    3. TOCTOU: os números usados para decidir QUAIS/QUANTOS slots fechar
       devem vir de uma leitura de `entries` feita já dentro do lock.
    4. Fecha do slot mais recente para o mais antigo até eliminar phantom.
    """

    def test_dry_run_returns_zero_without_querying_exchange(self):
        agent = _make_agent(entries=[_entry(90_000, 0.001)], dry_run=True)
        with patch.object(kucoin_api, "get_balance") as mock_balance:
            result = agent._reconcile_position_with_exchange()
        assert result == 0
        mock_balance.assert_not_called()

    def test_no_entries_returns_zero(self):
        agent = _make_agent(entries=[], dry_run=False)
        with patch.object(kucoin_api, "get_balance") as mock_balance:
            result = agent._reconcile_position_with_exchange()
        assert result == 0
        mock_balance.assert_not_called()

    def test_consistent_within_tolerance_returns_zero_no_alert(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001)]
        agent = _make_agent(entries=entries, dry_run=False)
        with (
            patch.object(kucoin_api, "get_balance", return_value=0.002),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange()
        assert result == 0
        assert len(agent.state.entries) == 2
        mock_alert.assert_not_called()

    def test_exchange_greater_than_db_alerts_and_does_not_mutate_entries(self):
        """Conta compartilhada: exchange com MAIS moeda só alerta."""
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(entries=entries, dry_run=False)
        with (
            patch.object(kucoin_api, "get_balance", return_value=0.010),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange()
        assert result == 0
        assert len(agent.state.entries) == 1  # nada mudou no state
        mock_alert.assert_called_once()
        message = mock_alert.call_args.args[0]
        assert "mais" in message.lower()
        assert "BTC" in message
        assert "Sem ação automática" in message

    def test_exclusive_balance_applies_excess_to_latest_open_buy(self):
        """ETH-USDT/aggressive: subconta dedicada adota o excesso no lote."""
        lot = _entry(1_957.09, 0.03147046)
        lot["trade_id"] = 3901
        agent = _make_agent(
            entries=[lot],
            dry_run=False,
            live_cfg={"kucoin_require_dedicated_credentials": True},
        )
        agent.symbol = "ETH-USDT"
        agent.db.update_trade_fill.return_value = True
        with (
            patch.object(kucoin_api, "get_balance", return_value=0.03177560),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange(current_price=1_882.36)
        assert result == 0
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["size"] == pytest.approx(0.03177560)
        assert agent.state.position == pytest.approx(0.03177560)
        agent.db.update_trade_fill.assert_called_once()
        mock_alert.assert_called_once()
        assert "efetiva" in mock_alert.call_args.args[0].lower()
        agent.db.record_trade.assert_not_called()

    def test_exclusive_balance_without_trade_id_records_new_lot(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            entries=entries,
            dry_run=False,
            live_cfg={"kucoin_require_dedicated_credentials": True},
        )
        agent.db.record_trade.return_value = 77
        with (
            patch.object(kucoin_api, "get_balance", return_value=0.0013),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange(current_price=90_000.0)
        assert result == 0
        assert len(agent.state.entries) == 2
        assert agent.state.entries[-1]["trade_id"] == 77
        assert agent.state.entries[-1]["size"] == pytest.approx(0.0003)
        agent.db.record_trade.assert_called_once()
        assert "efetiva" in mock_alert.call_args.args[0].lower()

    def test_exclusive_secret_name_adopts_excess_when_entries_empty(self):
        agent = _make_agent(entries=[], dry_run=False)
        agent.symbol = "ETH-USDT"
        agent.db.record_trade.return_value = 88
        with (
            patch.dict(os.environ, {"KUCOIN_SECRET_NAMES": "kucoin/sub-ethagressive"}),
            patch.object(kucoin_api, "get_balance", return_value=0.00030514),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange(current_price=1_882.36)
        assert result == 0
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["size"] == pytest.approx(0.00030514)
        assert "efetiva" in mock_alert.call_args.args[0].lower()

    def test_exchange_excess_restores_exact_persistent_buy_for_configured_subaccount(self):
        """O saldo extra só readota o BUY identificado por profile/subconta/order.

        Regressão do incidente BTC conservative: a ordem antiga permaneceu no
        ledger, mas ficou fora de state.entries após uma reconciliação anterior.
        """
        recent = _entry(63_228.65, 0.0002369969942423253)
        recent.update({"trade_id": 3831, "order_id": "recent-order"})
        agent = _make_agent(
            position=recent["size"],
            entries=[recent],
            dry_run=False,
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )
        agent.db.get_reconciliable_open_buys.return_value = [{
            "id": 3619,
            "order_id": "6a5fa9cb0e7dfc0007432e07",
            "price": 66_461.35,
            "size": 0.00022546938935185637,
            "timestamp": 1_784_647_085.0,
            "metadata": {"target_sell_price": 67_325.35},
        }]
        agent.db.mark_open_buy_restored.return_value = True

        bal = [{
            "sub_name": "BTCConservative",
            "account_type": "trade",
            "currency": "BTC",
            "available": 0.00046246638359418165,
        }]
        with ExitStack() as stack:
            for cm in _subaccount_balance_patches(bal):
                stack.enter_context(cm)
            mock_alert = stack.enter_context(
                patch.object(position_manager_mixin, "_send_telegram_alert")
            )
            result = agent._reconcile_position_with_exchange()

        assert result == 0
        assert len(agent.state.entries) == 2
        restored = agent.state.entries[-1]
        assert restored["trade_id"] == 3619
        assert restored["order_id"] == "6a5fa9cb0e7dfc0007432e07"
        assert restored["size"] == pytest.approx(0.00022546938935185637)
        assert restored["target_sell"] == pytest.approx(67_325.35)
        agent.db.mark_open_buy_restored.assert_called_once_with(
            3619,
            "BTC-USDT",
            "conservative",
            "BTCConservative",
            "6a5fa9cb0e7dfc0007432e07",
        )
        mock_alert.assert_not_called()

    def test_exchange_excess_without_subaccount_never_adopts_persistent_buy(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(entries=entries, dry_run=False, live_cfg={})

        with (
            patch.object(kucoin_api, "get_balance", return_value=0.002),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange()

        assert result == 0
        assert len(agent.state.entries) == 1
        agent.db.get_reconciliable_open_buys.assert_not_called()
        agent.db.mark_open_buy_restored.assert_not_called()
        mock_alert.assert_called_once()

    def test_exchange_excess_with_multiple_candidates_adopts_exclusive_lot(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            entries=entries,
            dry_run=False,
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )
        agent.db.get_reconciliable_open_buys.return_value = [
            {"id": 10, "order_id": "order-a", "price": 90_000, "size": 0.001},
            {"id": 11, "order_id": "order-b", "price": 90_000, "size": 0.001},
        ]

        bal = [{
            "sub_name": "BTCConservative",
            "account_type": "trade",
            "currency": "BTC",
            "available": 0.002,
        }]
        with ExitStack() as stack:
            for cm in _subaccount_balance_patches(bal):
                stack.enter_context(cm)
            mock_alert = stack.enter_context(
                patch.object(position_manager_mixin, "_send_telegram_alert")
            )
            result = agent._reconcile_position_with_exchange()

        assert result == 0
        # Subconta exclusiva: se o BUY persistente é ambíguo, o excesso
        # ainda é adotado (lote novo) — reconciliação efetiva.
        assert len(agent.state.entries) == 2
        agent.db.mark_open_buy_restored.assert_not_called()
        mock_alert.assert_called_once()
        assert "efetiva" in mock_alert.call_args.args[0].lower()

    def test_persistent_claim_failure_adopts_exclusive_excess(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            entries=entries,
            dry_run=False,
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )
        agent.db.get_reconciliable_open_buys.return_value = [
            {"id": 10, "order_id": "order-a", "price": 90_000, "size": 0.001},
        ]
        agent.db.mark_open_buy_restored.return_value = False

        bal = [{
            "sub_name": "BTCConservative",
            "account_type": "trade",
            "currency": "BTC",
            "available": 0.002,
        }]
        with ExitStack() as stack:
            for cm in _subaccount_balance_patches(bal):
                stack.enter_context(cm)
            mock_alert = stack.enter_context(
                patch.object(position_manager_mixin, "_send_telegram_alert")
            )
            result = agent._reconcile_position_with_exchange()

        assert result == 0
        assert len(agent.state.entries) == 2
        mock_alert.assert_called_once()
        assert "efetiva" in mock_alert.call_args.args[0].lower()

    def test_configured_subaccount_uses_available_balance_not_total_balance(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            entries=entries,
            dry_run=False,
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )

        bal = [{
            "sub_name": "BTCConservative",
            "account_type": "trade",
            "currency": "BTC",
            "balance": 0.002,
            "available": 0.001,
        }]
        with ExitStack() as stack:
            for cm in _subaccount_balance_patches(bal):
                stack.enter_context(cm)
            mock_alert = stack.enter_context(
                patch.object(position_manager_mixin, "_send_telegram_alert")
            )
            result = agent._reconcile_position_with_exchange()

        assert result == 0
        agent.db.get_reconciliable_open_buys.assert_not_called()
        mock_alert.assert_not_called()

    def test_configured_subaccount_zero_balance_closes_phantom_entries(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            entries=entries,
            dry_run=False,
            live_cfg={"kucoin_subaccount_name": "BTCConservative"},
        )

        bal = [{
            "sub_name": "BTCConservative",
            "account_type": "trade",
            "currency": "BTC",
            "balance": 0.0,
            "available": 0.0,
        }]
        with ExitStack() as stack:
            for cm in _subaccount_balance_patches(bal):
                stack.enter_context(cm)
            result = agent._reconcile_position_with_exchange(current_price=90_000.0)

        assert result == 1
        assert agent.state.entries == []

    def test_db_greater_than_exchange_closes_most_recent_slots_first(self):
        entries = [
            _entry(88_000, 0.001),  # mais antigo — deve sobreviver
            _entry(90_000, 0.001),  # mais recente — deve ser fechado
        ]
        agent = _make_agent(entries=entries, dry_run=False)
        with (
            patch.object(kucoin_api, "get_balance", return_value=0.001),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange(current_price=90_000.0)
        assert result == 1
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["price"] == 88_000
        mock_alert.assert_not_called()

    def test_toctou_uses_fresh_entries_read_inside_lock_not_stale_prelock_snapshot(self):
        """Regressão do achado #3: simula um trade concorrente que remove
        um entry (via efeito colateral no get_price, chamado ENTRE a
        checagem pré-lock e a aquisição do lock) tornando a posição já
        consistente. Se o código (incorretamente) confiasse nos números
        pré-lock, fecharia o entry restante (fantasma calculado com dados
        obsoletos); com o fix, a releitura dentro do lock detecta que já
        está tudo consistente e não fecha nada."""
        entry_a = _entry(88_000, 0.001)
        entry_b = _entry(90_000, 0.001)
        agent = _make_agent(entries=[entry_a, entry_b], dry_run=False)
        # real_balance fixo em 0.001: no snapshot pré-lock (2 entries =
        # 0.002 db_position) isso pareceria phantom=0.001 (1 entry sobra).
        # Mas um "trade concorrente" remove entry_b antes do lock ser
        # adquirido — deixando db_position real = 0.001 == real_balance.
        def _simulate_concurrent_trade_removing_entry_b(*_a, **_kw):
            agent.state.entries = [entry_a]
            return 90_000.0

        with (
            patch.object(kucoin_api, "get_balance", return_value=0.001),
            patch.object(
                kucoin_api, "get_price",
                side_effect=_simulate_concurrent_trade_removing_entry_b,
            ),
            patch.object(position_manager_mixin, "_send_telegram_alert") as mock_alert,
        ):
            result = agent._reconcile_position_with_exchange()

        assert result == 0, "TOCTOU: fechou um slot usando phantom_btc obsoleto (pré-lock)"
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0] is entry_a
        mock_alert.assert_not_called()
