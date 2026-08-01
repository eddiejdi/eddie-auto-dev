import sys
from pathlib import Path

_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

from position_reconstruction import reconstruct_open_buys


def _trade(
    trade_id: int,
    side: str,
    price: float,
    size: float,
    *,
    metadata: dict | None = None,
    dry_run: bool = False,
) -> dict:
    return {
        "id": trade_id,
        "side": side,
        "price": price,
        "size": size,
        "timestamp": float(trade_id),
        "metadata": metadata or {},
        "dry_run": dry_run,
    }


def test_reconstruct_open_buys_excludes_external_deposit() -> None:
    trades = [
        _trade(3, "buy", 101.0, 0.003, metadata={"source": "external_deposit"}),
        _trade(2, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, exclude_external_deposits=True)

    assert [trade["id"] for trade in open_buys] == [2]


def test_reconstruct_open_buys_consumes_slot_sell_by_trade_id() -> None:
    trades = [
        _trade(
            30,
            "sell",
            105.0,
            0.001,
            metadata={
                "slot_exit_reason": "PER_SLOT_TP",
                "slot_buy_trade_id": 10,
                "slot_entry_price": 100.0,
            },
        ),
        _trade(11, "buy", 101.0, 0.001),
        _trade(10, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades)

    assert [trade["id"] for trade in open_buys] == [11]


def test_reconstruct_open_buys_shared_ambiguous_blind_sell_closes_by_size_not_flatten() -> None:
    """Regressão do achado real de produção (2026-08-01, DOGE-USDT shadow):

    Um SELL "cego" (sem slot_exit_reason) fecha exatamente o volume que
    vendeu — não "tudo que veio antes dele". Antes desse fix, QUALQUER sell
    cego mais recente (mesmo fechando só 1 entrada) descartava todas as
    entradas mais antigas do scan, escondendo posições ainda abertas e
    vendíveis. Aqui o sell de 0.001 fecha só a compra 19 (mesmo tamanho);
    a compra 18, mais antiga, continua aberta.
    """
    trades = [
        _trade(20, "sell", 105.0, 0.001),
        _trade(19, "buy", 101.0, 0.001),
        _trade(18, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert [trade["id"] for trade in open_buys] == [18]


def test_reconstruct_open_buys_blind_sell_never_matches_a_newer_buy() -> None:
    """Causalidade: um SELL cego só pode fechar BUYs mais antigos que ele —
    nunca um BUY mais novo (que aconteceu DEPOIS do sell, cronologicamente).
    """
    trades = [
        _trade(23, "buy", 103.0, 0.001),
        _trade(22, "sell", 105.0, 0.001),
        _trade(21, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert [trade["id"] for trade in open_buys] == [23]


def test_reconstruct_open_buys_blind_sell_size_tolerance_covers_fee_rounding() -> None:
    """Tolerância de 0,2% cobre a diferença real observada em produção entre
    o size nominal da compra e o size líquido vendido (fees/rounding) — sem
    isso, esse tipo de venda ficaria permanentemente "curta" e a compra
    nunca seria dada como fechada.
    """
    trades = [
        _trade(2, "sell", 105.0, 134.5001),
        _trade(1, "buy", 100.0, 134.6076),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert open_buys == []


def test_reconstruct_open_buys_shared_ambiguous_keeps_recent_buy_streak_only() -> None:
    trades = [
        _trade(25, "buy", 103.0, 0.001),
        _trade(24, "buy", 102.0, 0.001),
        _trade(23, "sell", 104.0, 0.001),
        _trade(22, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert [trade["id"] for trade in open_buys] == [25, 24]


def test_reconstruct_open_buys_shared_ambiguous_partial_slot_sell_keeps_older_entries() -> None:
    """Regressão: um SELL por slot em conta compartilhada não pode "esquecer"
    entradas mais antigas que ele não fechou — só um SELL cego (sem
    slot_exit_reason) representa flatten global."""
    trades = [
        _trade(
            33,
            "sell",
            110.0,
            0.001,
            metadata={
                "slot_exit_reason": "PER_SLOT_TP",
                "slot_buy_trade_id": 32,
                "slot_entry_price": 103.0,
            },
        ),
        _trade(32, "buy", 103.0, 0.001),
        _trade(31, "buy", 102.0, 0.001),
        _trade(30, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert [trade["id"] for trade in open_buys] == [31, 30]


def test_reconstruct_open_buys_shared_ambiguous_disables_price_matching() -> None:
    """Em conta compartilhada, sells por slot sem slot_buy_trade_id não podem
    casar por preço — preços podem colidir com buys de outro profile na mesma
    subconta. Nesse caso o slot vira 'blind' e consome a compra mais antiga
    disponível na ordem de varredura, não uma por coincidência de preço."""
    trades = [
        _trade(
            43,
            "sell",
            110.0,
            0.001,
            metadata={"slot_exit_reason": "PER_SLOT_TP", "slot_entry_price": 100.0},
        ),
        _trade(42, "buy", 103.0, 0.001),
        _trade(41, "buy", 100.0, 0.001),
    ]

    open_buys = reconstruct_open_buys(trades, shared_profile_ambiguous=True)

    assert [trade["id"] for trade in open_buys] == [41]


def test_reconstruct_open_buys_preserves_dry_run_flag() -> None:
    """dry_run do BUY original deve ser propagado para o entry dict.

    Sem isso, a reconciliação de slots fantasma registra perdas de posições
    simuladas como trades live, corrompendo o PnL real do perfil.
    """
    trades = [
        _trade(2, "buy", 65000.0, 0.001, dry_run=True),
        _trade(1, "buy", 64000.0, 0.001, dry_run=False),
    ]

    open_buys = reconstruct_open_buys(trades)

    assert len(open_buys) == 2
    dry_flags = {t["id"]: t["dry_run"] for t in open_buys}
    assert dry_flags[1] is False
    assert dry_flags[2] is True
