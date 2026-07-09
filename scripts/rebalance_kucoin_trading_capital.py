#!/usr/bin/env python3
"""Remaneja USDT entre master TRADE e subcontas KuCoin para a frota operar.

Política:
- Subcontas (BTC/ETH live): manter TARGET_SUB_USDT cada (~$22-25).
- Master TRADE (shadows BTC/ETH + SOL×3): concentrar o excedente das subs.
- ETHAgressive recebe top-up se estiver abaixo do mínimo.

Uso:
    python3 scripts/rebalance_kucoin_trading_capital.py --dry-run
    python3 scripts/rebalance_kucoin_trading_capital.py --execute
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "btc_trading_agent"
for p in (ROOT, AGENT_DIR, Path("/apps/crypto-trader/trading/btc_trading_agent")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

import kucoin_api as k  # noqa: E402

TARGET_SUB_USDT = 23.0
MIN_SUB_USDT = 18.0
SUB_TOPUP_FROM_MASTER = 5.0

# userId interno (GET /api/v2/sub/user) — não usar uid da UI
SUB_USER_IDS = {
    "BTCAgressive": "6a2fe102dc143e00017b48fe",
    "BTCConservative": "6a2fe6f634e4a40001c3a385",
    "ETHAgressive": "6a4849435769ca0001652fdf",
    "ETHConservative": "6a484a6d5769ca000165306d",
}


@dataclass(frozen=True)
class TransferPlan:
    direction: str  # OUT=master→sub, IN=sub→master
    sub_name: str
    amount: float
    reason: str


def _master_trade_usdt() -> float:
    for b in k.get_balances(account_type="trade"):
        if b["currency"] == "USDT":
            return float(b["available"])
    return 0.0


def _sub_trade_usdt() -> dict[str, float]:
    out: dict[str, float] = {}
    for row in k.get_sub_account_balances():
        if row["account_type"] == "trade" and row["currency"] == "USDT":
            out[row["sub_name"]] = float(row["available"])
    return out


def build_plan() -> list[TransferPlan]:
    subs = _sub_trade_usdt()
    plans: list[TransferPlan] = []

    # 1) Top-up subcontas abaixo do mínimo (via master, depois das coletas)
    eth_agg = subs.get("ETHAgressive", 0.0)
    if eth_agg < MIN_SUB_USDT:
        plans.append(
            TransferPlan(
                "OUT",
                "ETHAgressive",
                round(min(SUB_TOPUP_FROM_MASTER, TARGET_SUB_USDT - eth_agg), 2),
                f"ETHAgressive abaixo do mínimo ({eth_agg:.2f} < {MIN_SUB_USDT})",
            )
        )

    # 2) Sweep excedente das subs para master TRADE
    for name, avail in sorted(subs.items()):
        if avail <= TARGET_SUB_USDT:
            continue
        excess = round(avail - TARGET_SUB_USDT, 2)
        if excess >= 1.0:
            plans.append(
                TransferPlan(
                    "IN",
                    name,
                    excess,
                    f"excedente acima de ${TARGET_SUB_USDT:.0f} (avail=${avail:.2f})",
                )
            )

    # Executar coletas (IN) antes de desembolsos (OUT) na prática
    plans.sort(key=lambda p: (0 if p.direction == "IN" else 1, p.sub_name))
    return plans


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Aplica transferências (padrão: dry-run)")
    args = parser.parse_args()
    execute = bool(args.execute)

    master_before = _master_trade_usdt()
    subs_before = _sub_trade_usdt()
    plans = build_plan()

    print("=== Saldos atuais (TRADE USDT) ===")
    print(f"  master TRADE: ${master_before:.2f}")
    for name, amt in sorted(subs_before.items()):
        print(f"  sub:{name}: ${amt:.2f}")

    print("\n=== Plano de remanejamento ===")
    if not plans:
        print("  (nenhuma transferência necessária)")
        return 0

    projected_master = master_before
    projected_subs = dict(subs_before)
    for plan in plans:
        uid = SUB_USER_IDS.get(plan.sub_name, "?")
        arrow = "sub→master" if plan.direction == "IN" else "master→sub"
        print(
            f"  {arrow} {plan.sub_name}: ${plan.amount:.2f}  "
            f"[{plan.reason}]  userId={uid}"
        )
        if plan.direction == "IN":
            projected_master += plan.amount
            projected_subs[plan.sub_name] = projected_subs.get(plan.sub_name, 0) - plan.amount
        else:
            projected_master -= plan.amount
            projected_subs[plan.sub_name] = projected_subs.get(plan.sub_name, 0) + plan.amount

    print("\n=== Projeção pós-remanejamento ===")
    print(f"  master TRADE: ${projected_master:.2f}")
    for name, amt in sorted(projected_subs.items()):
        print(f"  sub:{name}: ${amt:.2f}")

    if not execute:
        print("\n(dry-run — use --execute para aplicar)")
        return 0

    print("\n=== Executando transferências ===")
    results = []
    for plan in plans:
        uid = SUB_USER_IDS[plan.sub_name]
        result = k.sub_transfer(
            "USDT",
            plan.amount,
            uid,
            direction=plan.direction,
            account_type="TRADE",
            sub_account_type="TRADE",
        )
        ok = result.get("success", False)
        results.append((plan, result))
        status = "OK" if ok else f"FAIL: {result.get('error')}"
        print(f"  {plan.sub_name} {plan.direction} ${plan.amount:.2f}: {status}")
        if not ok:
            print(json.dumps(result, indent=2))
            return 1

    print("\n=== Saldos finais ===")
    print(f"  master TRADE: ${_master_trade_usdt():.2f}")
    for name, amt in sorted(_sub_trade_usdt().items()):
        print(f"  sub:{name}: ${amt:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())