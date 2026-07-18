#!/usr/bin/env python3
"""CLI read-only: encontra rota de menor custo entre duas moedas.

Uso:
  python route_cli.py ETH BTC 0.05
  python -m btc_trading_agent.route_cli SOL USDT 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from route_graph import RouteOptions, compare_routes, find_best_route, savings_vs_usdt_bps


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="KuCoin intercoin route planner (read-only)")
    p.add_argument("asset_in", help="Moeda de origem (ex: ETH)")
    p.add_argument("asset_out", help="Moeda de destino (ex: BTC)")
    p.add_argument("amount", type=float, help="Quantidade na moeda de origem")
    p.add_argument("--max-hops", type=int, default=2)
    p.add_argument("--max-spread-bps", type=float, default=50.0)
    p.add_argument("--min-vol-usd", type=float, default=0.0, help="0 = não filtrar por volume")
    p.add_argument("--allow-exotic", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    opts = RouteOptions(
        max_hops=args.max_hops,
        max_spread_bps=args.max_spread_bps,
        min_pair_vol_usd=args.min_vol_usd,
        allow_exotic_hubs=args.allow_exotic,
        use_live_fees=False,  # CLI pública: fallback fee sem auth
    )
    candidates = compare_routes(args.asset_in, args.asset_out, args.amount, opts=opts)
    best = find_best_route(args.asset_in, args.asset_out, args.amount, opts=opts)
    sav = savings_vs_usdt_bps(best, candidates) if best else None

    if args.json:
        print(
            json.dumps(
                {
                    "best": best.to_dict() if best else None,
                    "savings_vs_usdt_bps": sav,
                    "candidates": [c.to_dict() for c in candidates[:5]],
                },
                indent=2,
            )
        )
        return 0 if best else 1

    if not best:
        print(f"Nenhuma rota {args.asset_in}→{args.asset_out} amount={args.amount}")
        return 1

    print(f"Melhor rota {args.asset_in} → {args.asset_out} ({args.amount})")
    print(f"  via={best.via} hops={best.hops} cost={best.total_cost_pct*10000:.2f} bps")
    print(f"  est_out={best.est_out:.10f} {args.asset_out} score={best.score:.6f}")
    if sav is not None:
        print(f"  savings_vs_usdt={sav:.2f} bps")
    for i, leg in enumerate(best.legs):
        print(
            f"  leg{i}: {leg.side} {leg.symbol} in={leg.amount_in:.8f} "
            f"out≈{leg.est_out:.8f} fee={leg.fee_pct*100:.3f}% spread={leg.spread_bps:.2f}bps"
        )
    if len(candidates) > 1:
        print("\nOutros candidatos:")
        for c in candidates[1:4]:
            print(
                f"  - {c.via} hops={c.hops} cost={c.total_cost_pct*10000:.2f}bps "
                f"out={c.est_out:.10f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
