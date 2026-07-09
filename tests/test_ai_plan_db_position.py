"""Testes: cenário SOL — posição no DB alinhada ao Grafana/exporter."""

from __future__ import annotations

from btc_trading_agent.position_reconstruction import (
    reconstruct_open_buys,
    summarize_open_buys,
)


def test_sol_conservative_open_buy_matches_grafana_logic() -> None:
    """BUY live SOL conservative deve aparecer como posição aberta."""
    trades = [
        {
            "id": 3318,
            "side": "buy",
            "size": 0.128,
            "price": 77.66,
            "timestamp": 1783564012.0,
            "metadata": {"target_sell_price": 78.67, "source": "kucoin_sync"},
            "dry_run": False,
        }
    ]
    open_buys = reconstruct_open_buys(
        trades,
        shared_profile_ambiguous=True,
        exclude_external_deposits=True,
    )
    total_size, avg_entry = summarize_open_buys(open_buys)

    assert len(open_buys) == 1
    assert total_size == 0.128
    assert avg_entry == 77.66