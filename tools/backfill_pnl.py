#!/usr/bin/env python3
"""Backfill PnL para sells que não tiveram cálculo (exchange_sync e aggressive).

Usa FIFO matching: para cada sell (por profile+symbol), consome buys anteriores
na ordem cronológica e calcula PnL descontando fees de 0.1%.

Modo: dry-run por padrão. Use --apply para persistir.
"""
import argparse
import sys
from collections import deque
from pathlib import Path
from typing import Any

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "btc_trading_agent"))

TRADING_FEE_PCT = 0.001  # 0.1% fee


def get_connection():
    """Obtém conexão PostgreSQL via secrets_helper."""
    try:
        from secrets_helper import get_database_url
        url = get_database_url()
    except Exception:
        import os
        url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("❌ DATABASE_URL não configurado.")
        sys.exit(1)

    import psycopg2
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def fetch_trades(conn, profile: str, symbol: str = "BTC-USDT") -> list[dict[str, Any]]:
    """Busca todos os trades de um profile, ordenados por timestamp."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp, side, price, size, pnl
        FROM btc.trades
        WHERE profile = %s AND symbol = %s AND dry_run = false
        ORDER BY timestamp ASC
    """, (profile, symbol))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fifo_pnl(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calcula PnL via FIFO para sells sem pnl preenchido.

    Retorna lista de updates: [{id, pnl, pnl_pct}, ...]
    """
    buy_queue: deque[dict[str, float]] = deque()
    updates: list[dict[str, Any]] = []

    for t in trades:
        if t["side"] == "buy":
            buy_queue.append({"price": float(t["price"]), "remaining": float(t["size"])})
        elif t["side"] == "sell" and t["pnl"] is None:
            sell_price = float(t["price"])
            sell_size = float(t["size"])
            remaining = sell_size
            weighted_entry = 0.0

            # Consumir buys FIFO
            while remaining > 1e-12 and buy_queue:
                buy = buy_queue[0]
                take = min(buy["remaining"], remaining)
                weighted_entry += buy["price"] * take
                buy["remaining"] -= take
                remaining -= take
                if buy["remaining"] < 1e-12:
                    buy_queue.popleft()

            if sell_size < 1e-12:
                continue

            matched_size = sell_size - remaining
            if matched_size < 1e-12:
                # Sem buys correspondentes para match
                print(f"  ⚠️  Trade #{t['id']}: sem buys para match ({sell_size:.8f} BTC)")
                continue

            avg_entry = weighted_entry / matched_size
            gross_pnl = (sell_price - avg_entry) * matched_size
            sell_fee = sell_price * matched_size * TRADING_FEE_PCT
            buy_fee = avg_entry * matched_size * TRADING_FEE_PCT
            pnl = gross_pnl - sell_fee - buy_fee

            net_sell = sell_price * (1 - TRADING_FEE_PCT)
            net_buy = avg_entry * (1 + TRADING_FEE_PCT)
            pnl_pct = ((net_sell / net_buy) - 1) * 100 if net_buy > 0 else 0

            updates.append({
                "id": t["id"],
                "pnl": round(pnl, 10),
                "pnl_pct": round(pnl_pct, 6),
                "sell_price": sell_price,
                "avg_entry": round(avg_entry, 2),
                "size": matched_size,
            })
        # sells que já têm pnl: consumir buys normalmente para manter FIFO
        elif t["side"] == "sell" and t["pnl"] is not None:
            sell_size = float(t["size"])
            remaining = sell_size
            while remaining > 1e-12 and buy_queue:
                buy = buy_queue[0]
                take = min(buy["remaining"], remaining)
                buy["remaining"] -= take
                remaining -= take
                if buy["remaining"] < 1e-12:
                    buy_queue.popleft()

    return updates


def main():
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(description="Backfill PnL para sells sem cálculo")
    parser.add_argument("--apply", action="store_true", help="Persistir no banco (default: dry-run)")
    parser.add_argument("--profiles", nargs="+", default=["exchange_sync", "aggressive"],
                        help="Profiles para processar")
    parser.add_argument("--symbol", default="BTC-USDT", help="Symbol (default: BTC-USDT)")
    args = parser.parse_args()

    conn = get_connection()
    total_updates = 0
    total_pnl = 0.0

    for profile in args.profiles:
        print(f"\n{'='*60}")
        print(f"Profile: {profile} | Symbol: {args.symbol}")
        print(f"{'='*60}")

        trades = fetch_trades(conn, profile, args.symbol)
        buys = [t for t in trades if t["side"] == "buy"]
        sells_no_pnl = [t for t in trades if t["side"] == "sell" and t["pnl"] is None]

        print(f"  Total trades: {len(trades)} | Buys: {len(buys)} | Sells sem PnL: {len(sells_no_pnl)}")

        if not sells_no_pnl:
            print("  ✅ Nenhum sell sem PnL.")
            continue

        updates = fifo_pnl(trades)
        print(f"  📊 Updates calculados: {len(updates)}")

        for u in updates:
            direction = "🟢" if u["pnl"] >= 0 else "🔴"
            print(f"    {direction} #{u['id']}: entry=${u['avg_entry']:,.2f} → sell=${u['sell_price']:,.2f} "
                  f"| size={u['size']:.8f} | PnL=${u['pnl']:.4f} ({u['pnl_pct']:.2f}%)")

        profile_pnl = sum(u["pnl"] for u in updates)
        print(f"  💰 PnL total profile: ${profile_pnl:.4f}")
        total_pnl += profile_pnl
        total_updates += len(updates)

        if args.apply and updates:
            cur = conn.cursor()
            for u in updates:
                cur.execute(
                    "UPDATE btc.trades SET pnl = %s, pnl_pct = %s WHERE id = %s",
                    (u["pnl"], u["pnl_pct"], u["id"])
                )
            print(f"  ✅ {len(updates)} trades atualizados no banco!")

    print(f"\n{'='*60}")
    print(f"RESUMO: {total_updates} sells atualizados | PnL total: ${total_pnl:.4f}")
    if not args.apply and total_updates > 0:
        print("⚠️  Modo DRY-RUN. Use --apply para persistir.")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    main()
