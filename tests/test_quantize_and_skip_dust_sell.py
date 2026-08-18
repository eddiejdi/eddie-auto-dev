#!/usr/bin/env python3
"""Regressões do guard de SELL dust — baseMinSize / minFunds.

A KuCoin rejeita SELLs cujo size < baseMinSize com a mensagem
"The quantity is invalid." A falha reportada em produção (SOL-USDT
0.00043335 SOL, notional $0.03 USDT) vinha de slots fantasma criados
por ``_adopt_untracked_exchange_excess`` adotando resíduos de fill
abaixo do mínimo da exchange. Esses slots nunca seriam vendáveis.

Este guard:
  1. Em ``place_market_order``: não envia a ordem à KuCoin quando
     ``size < baseMinSize`` (side=sell). Retorna ``skipped=True`` sem
     chamar Telegram — silencioso, pois o alerta de dust é ruído.
  2. Em ``_execute_slot_sell``: ao receber ``skipped``, descarta o slot
     do state e marca a BUY de origem como closed no DB (metadata
     ``closed_reason=dust_below_baseMinSize``) — sem gravar SELL falsa.
  3. Em ``_adopt_untracked_exchange_excess``: rejeita adotar excesso
     cujo size seja menor que ``max(dust, baseMinSize)`` — não cria
     slot fantasma que a KuCoin rejeitaria.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import threading
import types
import unittest.mock as _mock

import pytest


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

BTC_DIR = Path(__file__).resolve().parents[1] / "btc_trading_agent"
sys.path.insert(0, str(BTC_DIR))
sys.modules.setdefault("httpx", types.SimpleNamespace())

_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)

_psycopg2_mock = types.ModuleType("psycopg2")
_psycopg2_mock.extras = types.SimpleNamespace(RealDictCursor=object)
_psycopg2_mock.pool = types.SimpleNamespace(
    ThreadedConnectionPool=object,
    SimpleConnectionPool=object,
)
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", _psycopg2_mock.extras)
sys.modules.setdefault("psycopg2.pool", _psycopg2_mock.pool)

sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(FastTradingModel=object, MarketState=object, Signal=object),
)

# Mock o kucoin_api no sys.modules para que o import de ``trading_agent`` não
# dispare o _load_credentials() (que faz HTTP ao Secrets Agent). Para os testes
# que exercitam ``place_market_order`` de verdade, carregamos o módulo real
# via importlib em ``_load_real_kucoin_api()`` com credenciais já setadas.
_FAKE_PMO = _mock.MagicMock(return_value={"success": True, "orderId": "x"})
_mock_kucoin = types.SimpleNamespace(
    get_price=None,
    get_price_fast=None,
    get_orderbook=None,
    get_candles=None,
    get_recent_trades=None,
    get_balances=None,
    get_balance=None,
    place_market_order=_FAKE_PMO,
    analyze_orderbook=None,
    analyze_trade_flow=None,
    inner_transfer=None,
    _has_keys=lambda: False,
    get_fills_for_order=lambda *a, **kw: {},
    get_symbol_min_size=lambda _s: {"baseMinSize": 0.0, "minFunds": 0.0},
    _resolve_telegram_bot_token=lambda: "",
    _resolve_telegram_chat_id=lambda: "",
    _resolve_telegram_thread_id=lambda: "",
    _send_telegram_alert=lambda *a, **kw: None,
)
sys.modules.setdefault("kucoin_api", _mock_kucoin)

import trading_agent as ta_mod
from trading_agent import BitcoinTradingAgent


@pytest.fixture(scope="module")
def real_kucoin_api(monkeypatch_module):
    """Carrega o ``kucoin_api.py`` real via importlib sem tocar a rede.

    O módulo real faz ``_load_credentials()`` no import — patcheamos
    ``secrets_helper.get_kucoin_credentials_with_source`` para retornar
    credenciais dummy antes do load, evitando 4 retries lentos ao
    Secrets Agent.
    """
    # Pré-popula env vars — o _load_credentials() ainda chama
    # get_kucoin_credentials_with_source(); se retornar credenciais
    # completas, sai imediato sem retry.
    secrets_helper_mock = types.ModuleType("secrets_helper")
    secrets_helper_mock.get_kucoin_credentials_with_source = lambda: ("k", "s", "p", "env")
    secrets_helper_mock.get_kucoin_credentials = lambda: ("k", "s", "p")
    secrets_helper_mock.clear_secret_cache = lambda: None
    secrets_helper_mock.get_secret = lambda *_a, **_kw: ""
    monkeypatch_module.setitem(sys.modules, "secrets_helper", secrets_helper_mock)

    if "kucoin_api_real" in sys.modules:
        return sys.modules["kucoin_api_real"]

    path = BTC_DIR / "kucoin_api.py"
    spec = importlib.util.spec_from_file_location("kucoin_api_real", str(path))
    module = importlib.util.module_from_spec(spec)
    # Evita que o import sobrescreva o mock em sys.modules["kucoin_api"].
    sys.modules["kucoin_api_real"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def monkeypatch_module():
    """``monkeypatch`` com escopo de módulo (compatível com pytest>=7).

    Garante que as patches aplicadas pela fixture ``real_kucoin_api``
    (``sys.modules["secrets_helper"]``, env vars) sobrevivam a todos os
    testes do módulo e sejam restauradas ao fim da sessão — sem vazar
    para outros arquivos de teste.
    """
    import pytest

    mpatch = pytest.MonkeyPatch()
    yield mpatch
    mpatch.undo()


# ──────────────────────────────────────────────────────────────────────────────
# Cenário real: SOL-USDT na KuCoin tem baseMinSize=0.01 e minFunds≈5.0.
# O resíduo 0.00043335 SOL (notional ~$0.03) estava sendo tentado em SELL
# — KuCoin rejeitava com "The quantity is invalid." e disparava Telegram.
# ──────────────────────────────────────────────────────────────────────────────
SOL_BASE_MIN_SIZE = 0.01
SOL_MIN_FUNDS = 5.0
SOL_DUST_RESIDUE = 0.00043335


def _entry(size=0.132, price=75.46, trade_id=3946, order_id="6a83d76513901300070c0c14"):
    return {
        "price": price,
        "size": size,
        "ts": 1_787_000_000.0,
        "target_sell": 0.0,
        "trailing_high": price,
        "trade_id": trade_id,
        "order_id": order_id,
    }


def _agent(entries=None, *, position=None, symbol="SOL-USDT", profile="aggressive"):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = symbol
    agent._trade_lock = threading.Lock()
    entries_list = list(entries if entries is not None else [_entry()])
    total = sum(e["size"] for e in entries_list)
    agent.state = SimpleNamespace(
        dry_run=False,
        profile=profile,
        position=position if position is not None else total,
        entry_price=75.46,
        entries=entries_list,
        position_count=len(entries_list),
        raw_entry_count=len(entries_list),
        logical_position_slots=len(entries_list),
        target_sell_price=0.0,
        target_sell_reason="",
        buy_success_pressure=0.0,
        buy_success_factor=1.0,
        buy_dynamic_batch_cap_usdt=0.0,
        dca_valley_low=0.0,
        trailing_high=75.46,
        total_pnl=0.0,
        winning_trades=0,
        total_trades=0,
        daily_trades=0,
        last_trade_time=0.0,
        last_sell_entry_price=0.0,
        last_sell_ts=0.0,
    )
    agent.db = _mock.MagicMock()
    agent.db.update_trade_fill.return_value = True
    agent._reconcile_position_with_exchange = _mock.MagicMock(return_value=0)
    agent._current_profile = _mock.MagicMock(return_value=profile)
    agent._sync_position_tracking = _mock.MagicMock()
    agent._post_sell_notify = _mock.MagicMock()
    return agent


# ──────────────────────────────────────────────────────────────────────────────
# place_market_order — guard silencioso de baseMinSize
# ──────────────────────────────────────────────────────────────────────────────

class TestPlaceMarketOrderDustSkip:
    """Guard em ``place_market_order``: SELL abaixo de baseMinSize é skip."""

    def _patch(self, monkeypatch, kapi, base_min=SOL_BASE_MIN_SIZE, min_funds=SOL_MIN_FUNDS):
        monkeypatch.setattr(
            kapi, "get_symbol_min_size",
            lambda _sym: {"baseMinSize": base_min, "minFunds": min_funds},
        )
        monkeypatch.setattr(kapi, "validate_credentials", lambda *a, **kw: None)
        # Garante que a cache de incrementos devolva um valor razoável.
        monkeypatch.setattr(
            kapi, "get_symbol_increments",
            lambda _s: {"baseIncrement": "0.00000001", "quoteIncrement": "0.01"},
        )

    def test_sell_below_baseMinSize_returns_skipped(self, real_kucoin_api, monkeypatch):
        self._patch(monkeypatch, real_kucoin_api)

        def _no_post(*a, **kw):
            raise AssertionError("POST nunca deveria ser chamado para dust")

        monkeypatch.setattr(real_kucoin_api, "_signed_request", _no_post)

        result = real_kucoin_api.place_market_order("SOL-USDT", "sell", size=SOL_DUST_RESIDUE)

        assert result["success"] is False
        assert result["skipped"] is True
        assert result["skip_reason"] == "below_baseMinSize"
        assert result["baseMinSize"] == SOL_BASE_MIN_SIZE

    def test_sell_below_baseMinSize_does_not_post_to_kucoin(self, real_kucoin_api, monkeypatch):
        self._patch(monkeypatch, real_kucoin_api)
        post_calls = []
        def _fake_post(*a, **kw):
            post_calls.append(1)
            raise AssertionError("POST nunca deveria ser chamado para dust")
        monkeypatch.setattr(real_kucoin_api, "_signed_request", _fake_post)

        real_kucoin_api.place_market_order("SOL-USDT", "sell", size=SOL_DUST_RESIDUE)
        assert post_calls == [], "KuCoin não deve ser chamada para SELL dust"

    def test_sell_below_baseMinSize_does_not_send_telegram(self, real_kucoin_api, monkeypatch):
        self._patch(monkeypatch, real_kucoin_api)
        telegram_calls = []
        monkeypatch.setattr(
            real_kucoin_api, "_send_telegram_alert",
            lambda *a, **kw: telegram_calls.append(1),
        )
        monkeypatch.setattr(
            real_kucoin_api, "_signed_request",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no post")),
        )

        real_kucoin_api.place_market_order("SOL-USDT", "sell", size=SOL_DUST_RESIDUE)
        assert telegram_calls == [], "Telegram não deve disparar para dust (sem alerta)"

    def test_sell_at_baseMinSize_passes_through_to_kucoin(self, real_kucoin_api, monkeypatch):
        """Exatamente no piso (size == baseMinSize) a ordem é enviada normalmente."""
        self._patch(monkeypatch, real_kucoin_api)
        fake_resp = _mock.MagicMock()
        fake_resp.json.return_value = {"code": "200000", "data": {"orderId": "ABC"}}
        monkeypatch.setattr(real_kucoin_api, "_signed_request", lambda *a, **kw: fake_resp)
        monkeypatch.setattr(real_kucoin_api, "get_order_by_client_oid", lambda _id: None)
        monkeypatch.setattr(real_kucoin_api, "_send_telegram_alert", lambda *a, **kw: None)

        result = real_kucoin_api.place_market_order("SOL-USDT", "sell", size=SOL_BASE_MIN_SIZE)
        assert result["success"] is True

    def test_sell_above_baseMinSize_passes_through(self, real_kucoin_api, monkeypatch):
        self._patch(monkeypatch, real_kucoin_api)
        fake_resp = _mock.MagicMock()
        fake_resp.json.return_value = {"code": "200000", "data": {"orderId": "ABC"}}
        monkeypatch.setattr(real_kucoin_api, "_signed_request", lambda *a, **kw: fake_resp)
        monkeypatch.setattr(real_kucoin_api, "get_order_by_client_oid", lambda _id: None)
        monkeypatch.setattr(real_kucoin_api, "_send_telegram_alert", lambda *a, **kw: None)

        # 0.132 SOL — acima de 0.01 baseMinSize (SOL-USDT normal).
        result = real_kucoin_api.place_market_order("SOL-USDT", "sell", size=0.132)
        assert result["success"] is True

    def test_buy_does_not_skip_on_small_size(self, real_kucoin_api, monkeypatch):
        """Compra nunca é bloqueada pelo guard de baseMinSize (só SELL)."""
        self._patch(monkeypatch, real_kucoin_api)
        fake_resp = _mock.MagicMock()
        fake_resp.json.return_value = {"code": "200000", "data": {"orderId": "ABC"}}
        monkeypatch.setattr(real_kucoin_api, "_signed_request", lambda *a, **kw: fake_resp)
        monkeypatch.setattr(real_kucoin_api, "get_order_by_client_oid", lambda _id: None)
        monkeypatch.setattr(real_kucoin_api, "_send_telegram_alert", lambda *a, **kw: None)

        # Mesmo um BUY de $0.5 não deve ser skipado — guard é só SELL.
        result = real_kucoin_api.place_market_order("SOL-USDT", "buy", funds=0.5)
        assert result["success"] is True

    def test_sell_below_minFunds_with_explicit_funds_is_skipped(self, real_kucoin_api, monkeypatch):
        self._patch(monkeypatch, real_kucoin_api, base_min=0.0, min_funds=SOL_MIN_FUNDS)
        monkeypatch.setattr(
            real_kucoin_api, "_signed_request",
            lambda *a, **kw: (_ for _ in ()).throw(AssertionError("nope")),
        )
        monkeypatch.setattr(real_kucoin_api, "_send_telegram_alert", lambda *a, **kw: None)

        result = real_kucoin_api.place_market_order("SOL-USDT", "sell", funds=0.5, size=0.001)
        # Sem baseMinSize, cai no branch de minFunds (notional explícito < 5).
        assert result.get("skipped") is True
        assert result["skip_reason"] == "below_minFunds"


# ──────────────────────────────────────────────────────────────────────────────
# _execute_slot_sell — descarta o slot dust ao receber skipped=True
# ──────────────────────────────────────────────────────────────────────────────

class TestExecuteSlotSellDustDiscard:
    """``_execute_slot_sell`` descarta o slot ao receber ``skipped=True``."""

    def _patch_pmo_skip(self, monkeypatch, result_override=None):
        skipped_result = result_override or {
            "success": False,
            "skipped": True,
            "skip_reason": "below_baseMinSize",
            "baseMinSize": SOL_BASE_MIN_SIZE,
            "size": SOL_DUST_RESIDUE,
            "error": "below_baseMinSize",
        }
        import position_manager_mixin as pmm
        monkeypatch.setattr(pmm, "place_market_order", lambda *a, **kw: skipped_result)

    def test_dust_slot_is_removed_from_entries(self, monkeypatch):
        self._patch_pmo_skip(monkeypatch)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])

        ok = agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        assert ok is True
        assert agent.state.entries == [], "slot dust deve ser removido"
        assert agent.state.position == 0.0

    def test_dust_slot_does_not_record_fake_sell(self, monkeypatch):
        """Não grava uma SELL falsa no DB — não houve execução na exchange."""
        self._patch_pmo_skip(monkeypatch)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])

        agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        # record_trade é para SELL; se gravou, é bug (estamos dizendo ao DB
        # que vendemos algo que a KuCoin nunca aceitou).
        assert agent.db.record_trade.call_count == 0
        assert agent.db.update_trade_pnl.call_count == 0

    def test_dust_slot_marks_origin_buy_closed_in_db(self, monkeypatch):
        """Marca a BUY de origem com closed_reason=dust_below_baseMinSize."""
        self._patch_pmo_skip(monkeypatch)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE, trade_id=3946)])

        agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        agent.db.merge_trade_metadata.assert_called_once()
        args, _ = agent.db.merge_trade_metadata.call_args
        trade_id_called, meta = args[0], args[1]
        assert trade_id_called == 3946
        assert meta["closed_reason"] == "dust_below_baseMinSize"
        assert meta["dust_size"] == round(SOL_DUST_RESIDUE, 8)

    def test_dust_slot_does_not_fire_post_sell_notify(self, monkeypatch):
        """Sem venda real → sem notificação Telegram do Ollama."""
        self._patch_pmo_skip(monkeypatch)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])

        agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        agent._post_sell_notify.assert_not_called()

    def test_other_slots_preserved_after_dust_discard(self, monkeypatch):
        """Slots maiores que baseMinSize permanecem — só o dust é removido."""
        self._patch_pmo_skip(monkeypatch)
        big_entry = _entry(size=0.132, price=75.46, trade_id=3946)
        dust_entry = _entry(size=SOL_DUST_RESIDUE, price=75.92, trade_id=3939)
        agent = _agent(entries=[big_entry, dust_entry])

        ok = agent._execute_slot_sell(1, price=76.43, reason="TP trigger")

        assert ok is True
        assert len(agent.state.entries) == 1
        # O slot restante é o grande (não o dust).
        assert agent.state.entries[0]["trade_id"] == 3946
        assert agent.state.position == 0.132

    def test_skip_reason_propagated_to_db_metadata(self, monkeypatch):
        """skip_reason do guard é propagado para o DB (auditoria)."""
        self._patch_pmo_skip(
            monkeypatch,
            result_override={
                "success": False,
                "skipped": True,
                "skip_reason": "below_minFunds",
                "minFunds": 5.0,
                "size": SOL_DUST_RESIDUE,
                "error": "below_minFunds",
            },
        )
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])

        agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        _, meta = agent.db.merge_trade_metadata.call_args[0]
        assert meta["dust_skip_reason"] == "below_minFunds"

    def test_db_failure_in_metadata_merge_does_not_raise(self, monkeypatch):
        """Falha ao marcar a BUY no DB não propaga — slot já foi removido."""
        self._patch_pmo_skip(monkeypatch)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])
        agent.db.merge_trade_metadata.side_effect = RuntimeError("db down")

        ok = agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        assert ok is True
        assert agent.state.entries == []

    def test_dry_run_does_not_trigger_dust_skip(self, monkeypatch):
        """Modo dry_run só loga — nunca chama place_market_order."""
        import position_manager_mixin as pmm
        called = {"pmo": 0}
        def _pmo_counter(*a, **kw):
            called["pmo"] += 1
            return {"success": True, "orderId": "x"}
        monkeypatch.setattr(pmm, "place_market_order", _pmo_counter)
        agent = _agent(entries=[_entry(size=SOL_DUST_RESIDUE)])
        agent.state.dry_run = True

        ok = agent._execute_slot_sell(0, price=76.43, reason="TP trigger")

        assert ok is True
        assert called["pmo"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# _adopt_untracked_exchange_excess — rejeita adotar excesso abaixo do baseMinSize
# ──────────────────────────────────────────────────────────────────────────────

class TestAdoptUntrackedExcessBaseMinSize:
    """``_adopt_untracked_exchange_excess`` não adota pó abaixo de baseMinSize."""

    def test_excess_below_baseMinSize_returns_false(self, monkeypatch):
        agent = _agent(entries=[_entry(size=0.132)], position=0.132)
        monkeypatch.setattr(
            BitcoinTradingAgent, "_min_tradeable_dust", lambda self: 0.00001
        )
        monkeypatch.setattr(
            BitcoinTradingAgent, "_base_min_size", lambda self: SOL_BASE_MIN_SIZE
        )

        ok = agent._adopt_untracked_exchange_excess(
            excess=SOL_DUST_RESIDUE,
            real_balance=0.13243335,
            db_position=0.132,
            current_price=75.46,
            profile="aggressive",
            subaccount="SOL_Aggressive",
            base_currency="SOL",
            tolerance=0.0001,
        )

        assert ok is False
        # Não deve criar slot no DB — ficaria como fantasma que a KuCoin rejeita.
        agent.db.record_trade.assert_not_called()

    def test_excess_above_baseMinSize_is_adopted(self, monkeypatch):
        """Acima do piso (e acima do dust) o fluxo de adoção segue normal."""
        agent = _agent(entries=[_entry(size=0.132)], position=0.132)
        monkeypatch.setattr(
            BitcoinTradingAgent, "_min_tradeable_dust", lambda self: 0.00001
        )
        monkeypatch.setattr(
            BitcoinTradingAgent, "_base_min_size", lambda self: SOL_BASE_MIN_SIZE
        )

        # Excesso de 0.05 SOL (> 0.01 baseMinSize) — adota como novo slot.
        ok = agent._adopt_untracked_exchange_excess(
            excess=0.05,
            real_balance=0.182,
            db_position=0.132,
            current_price=75.46,
            profile="aggressive",
            subaccount="SOL_Aggressive",
            base_currency="SOL",
            tolerance=0.0001,
        )

        assert ok is True
        # Nesse caminho o DB é atualizado (fill_adjust ou new_lot).
        assert agent.db.update_trade_fill.called or agent.db.record_trade.called

    def test_excess_below_config_dust_but_above_baseMinSize_uses_baseMinSize(
        self, monkeypatch
    ):
        """Quando config dust < baseMinSize, o piso efetivo é baseMinSize."""
        agent = _agent(entries=[_entry(size=0.132)], position=0.132)
        monkeypatch.setattr(
            BitcoinTradingAgent, "_min_tradeable_dust", lambda self: 0.00001
        )
        monkeypatch.setattr(
            BitcoinTradingAgent, "_base_min_size", lambda self: SOL_BASE_MIN_SIZE
        )

        # Excesso 0.005 — abaixo do baseMinSize (0.01) mas acima do dust (0.00001).
        ok = agent._adopt_untracked_exchange_excess(
            excess=0.005,
            real_balance=0.137,
            db_position=0.132,
            current_price=75.46,
            profile="aggressive",
            subaccount="SOL_Aggressive",
            base_currency="SOL",
            tolerance=0.0001,
        )

        assert ok is False, "deve rejeitar: 0.005 < baseMinSize 0.01"
        agent.db.record_trade.assert_not_called()
