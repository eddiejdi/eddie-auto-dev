#!/usr/bin/env python3
"""Remaneja USDT entre master TRADE e subcontas KuCoin para a frota operar.

Política:
- Subcontas (BTC/ETH live) abaixo de MIN_SUB_USDT recebem top-up até
  TARGET_SUB_USDT, priorizando a subconta com menor saldo primeiro.
- Master TRADE (shadows BTC/ETH + SOL×3): concentra o excedente das subs
  acima de TARGET_SUB_USDT, e nunca é drenado abaixo de MASTER_MIN_RESERVE_USDT.
- Cada execução move no máximo MAX_TRANSFER_TOTAL_PER_RUN_USDT — convergência
  gradual ao longo de várias rodadas (pensado para rodar via timer systemd),
  não um salto único.

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

TARGET_SUB_USDT = 30.0
MIN_SUB_USDT = 25.0
MASTER_MIN_RESERVE_USDT = 20.0
MAX_TRANSFER_TOTAL_PER_RUN_USDT = 15.0

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
    master = _master_trade_usdt()
    plans: list[TransferPlan] = []

    # 1) Sweep excedente das subs para master TRADE (não consome orçamento
    #    de OUT — na prática essas coletas acontecem antes dos desembolsos)
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
            master += excess

    # 2) Top-up das subcontas abaixo do mínimo, priorizando a mais baixa
    #    primeiro, respeitando a reserva mínima do master e o teto de
    #    transferência por execução.
    budget = round(min(MAX_TRANSFER_TOTAL_PER_RUN_USDT, master - MASTER_MIN_RESERVE_USDT), 2)
    if budget > 0:
        needy = sorted(
            ((name, avail) for name, avail in subs.items() if avail < MIN_SUB_USDT),
            key=lambda item: item[1],
        )
        for name, avail in needy:
            if budget <= 0:
                break
            amount = round(min(TARGET_SUB_USDT - avail, budget), 2)
            if amount < 1.0:
                continue
            plans.append(
                TransferPlan(
                    "OUT",
                    name,
                    amount,
                    f"{name} abaixo do mínimo ({avail:.2f} < {MIN_SUB_USDT})",
                )
            )
            budget = round(budget - amount, 2)

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