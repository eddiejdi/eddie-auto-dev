#!/usr/bin/env python3
"""
Monitor de Status do Agente de Trading (PostgreSQL)
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@172.17.0.2:5432/postgres"
)
SCHEMA = "btc"


def check_agent_status(dsn: str = None):
    """Verifica status do agente"""
    conn = psycopg2.connect(dsn or DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("📊 STATUS DO AGENTE DE TRADING")
    print("="*60)
    
    # Última atividade
    cursor.execute(f"SELECT MAX(timestamp) FROM {SCHEMA}.market_states")
    last_state_ts = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT MAX(timestamp) FROM {SCHEMA}.decisions")
    last_decision_ts = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT MAX(timestamp) FROM {SCHEMA}.trades")
    last_trade_ts = cursor.fetchone()[0]
    
    now = datetime.now().timestamp()
    
    print(f"\n⏰ ÚLTIMA ATIVIDADE:")
    if last_state_ts:
        delta = (now - last_state_ts) / 60
        status = "🟢 ATIVO" if delta < 1 else ("🟡 LENTO" if delta < 5 else "🔴 INATIVO")
        print(f"  • Market State: {datetime.fromtimestamp(last_state_ts).strftime('%Y-%m-%d %H:%M:%S')} "
              f"({delta:.1f} min atrás) {status}")
    else:
        print("  • Market State: Nenhum registro")
    
    if last_decision_ts:
        delta = (now - last_decision_ts) / 60
        print(f"  • Decisão: {datetime.fromtimestamp(last_decision_ts).strftime('%Y-%m-%d %H:%M:%S')} "
              f"({delta:.1f} min atrás)")
    else:
        print("  • Decisão: Nenhum registro")
    
    if last_trade_ts:
        delta = (now - last_trade_ts) / 60
        print(f"  • Trade: {datetime.fromtimestamp(last_trade_ts).strftime('%Y-%m-%d %H:%M:%S')} "
              f"({delta:.1f} min atrás)")
    else:
        print("  • Trade: Nenhum registro")
    
    # Estatísticas recentes (última hora)
    cutoff = now - 3600
    
    cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA}.market_states WHERE timestamp > %s", (cutoff,))
    recent_states = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA}.decisions WHERE timestamp > %s", (cutoff,))
    recent_decisions = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA}.trades WHERE timestamp > %s", (cutoff,))
    recent_trades = cursor.fetchone()[0]
    
    print(f"\n📈 ÚLTIMA HORA:")
    print(f"  • Market States: {recent_states}")
    print(f"  • Decisões: {recent_decisions}")
    print(f"  • Trades: {recent_trades}")
    
    # Últimas decisões
    cursor.execute(f"""
        SELECT timestamp, action, confidence, price
        FROM {SCHEMA}.decisions
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    decisions = cursor.fetchall()
    if decisions:
        print(f"\n🎯 ÚLTIMAS 5 DECISÕES:")
        for dec in decisions:
            ts = datetime.fromtimestamp(dec[0]).strftime('%H:%M:%S')
            action = dec[1]
            conf = dec[2]
            price = dec[3]
            emoji = "🟢" if action == "BUY" else ("🔴" if action == "SELL" else "⚪")
            print(f"  {emoji} {ts} | {action:4s} | {conf:5.1%} | ${price:,.2f}")
    
    # Últimos trades
    cursor.execute(f"""
        SELECT timestamp, side, price, size, pnl
        FROM {SCHEMA}.trades
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    trades = cursor.fetchall()
    if trades:
        print(f"\n💰 ÚLTIMOS 5 TRADES:")
        for trade in trades:
            ts = datetime.fromtimestamp(trade[0]).strftime('%H:%M:%S')
            side = trade[1]
            price = trade[2]
            size = trade[3]
            pnl = trade[4] if trade[4] else 0
            emoji = "🟢" if side == "buy" else "🔴"
            pnl_str = f"PnL: ${pnl:+.2f}" if pnl != 0 else ""
            print(f"  {emoji} {ts} | {side.upper():4s} | ${price:,.2f} | {size:.6f} BTC | {pnl_str}")
    
    cursor.close()
    conn.close()
    print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Monitor status do agente")
    parser.add_argument("--dsn", default=None,
                       help="PostgreSQL DSN (default: DATABASE_URL env)")
    parser.add_argument("--watch", action="store_true",
                       help="Watch mode (refresh every 10s)")
    
    args = parser.parse_args()
    
    if args.watch:
        import time
        try:
            while True:
                print("\033[2J\033[H")  # Clear screen
                check_agent_status(args.dsn)
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n👋 Bye!")
    else:
        check_agent_status(args.dsn)


if __name__ == "__main__":
    main()
