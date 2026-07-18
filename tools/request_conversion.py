#!/usr/bin/env python3
"""Enfileira conversão intermoedas para o owner USDT_BRL processar.

Uso:
  python tools/request_conversion.py --from ETH --to BTC --amount 0.01
  python tools/request_conversion.py --from BRL --to USDT --amount 100 --live
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "btc_trading_agent"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Enqueue intercoin conversion request")
    p.add_argument("--from", dest="asset_in", required=True)
    p.add_argument("--to", dest="asset_out", required=True)
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--min-out", type=float, default=None)
    p.add_argument("--profile", default="conservative")
    p.add_argument("--by", default="cli")
    p.add_argument("--live", action="store_true", help="Marca dry_run=false (executor ainda respeita config owner)")
    args = p.parse_args(argv)

    from training_db import TrainingDatabase

    db = TrainingDatabase()
    req_id = db.enqueue_conversion(
        asset_in=args.asset_in,
        asset_out=args.asset_out,
        amount_in=args.amount,
        min_out=args.min_out,
        requested_by=args.by,
        dry_run=not args.live,
        profile=args.profile,
        symbol_owner="USDT-BRL",
    )
    print(f"enqueued conversion_request id={req_id} {args.asset_in}→{args.asset_out} amount={args.amount}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
