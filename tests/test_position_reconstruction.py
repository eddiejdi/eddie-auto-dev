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


def test_reconstruct_open_buys_shared_ambiguous_latest_sell_means_flat() -> None:
    trades = [
        _trade(20, "sell", 105.0, 0.001),
        _trade(19, "buy", 101.0, 0.001),
        _trade(18, "buy", 100.0, 0.001),
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
