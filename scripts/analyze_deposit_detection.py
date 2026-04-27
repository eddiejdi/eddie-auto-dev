#!/usr/bin/env python3
"""Analisador de detecção de depósitos: identifica Fiat Deposits sem trades external_deposit."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from btc_trading_agent import secrets_helper


def main():
    """Conecta ao Postgres, compara depósitos vs trades, relata não-detectados."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ psycopg2 não instalado")
        return

    db_url = secrets_helper.get_database_url()
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Buscar todos os depósitos Fiat (últimos 30 dias para contexto)
        cur.execute(
            """
            SELECT 
                ledger_id, currency, amount, biz_type, direction, created_at_ms,
                to_timestamp(created_at_ms / 1000.0) AT TIME ZONE 'UTC' as created_at_utc
            FROM btc.exchange_account_ledgers 
            WHERE biz_type = 'Fiat Deposit' 
            AND created_at_ms > (EXTRACT(EPOCH FROM NOW()) - 30*24*3600)*1000
            ORDER BY created_at_ms DESC
            """
        )
        deposits = cur.fetchall()

        # 2. Buscar todos os trades external_deposit (últimos 30 dias)
        cur.execute(
            """
            SELECT 
                id, timestamp, to_timestamp(timestamp)::timestamptz as ts,
                side, size, order_id, metadata
            FROM btc.trades 
            WHERE (metadata->>'source') = 'external_deposit'
            AND timestamp > (EXTRACT(EPOCH FROM NOW()) - 30*24*3600)
            ORDER BY timestamp DESC
            """
        )
        trades = cur.fetchall()

        conn.close()

        # 3. Análise: agrupa trades por data, compara com depósitos
        deposit_dates = {}  # { date_str: [deposits] }
        trade_dates = {}    # { date_str: [trades] }

        for d in deposits:
            date_str = d['created_at_utc'].strftime('%Y-%m-%d')
            if date_str not in deposit_dates:
                deposit_dates[date_str] = []
            deposit_dates[date_str].append(d)

        for t in trades:
            date_str = t['ts'].strftime('%Y-%m-%d')
            if date_str not in trade_dates:
                trade_dates[date_str] = []
            trade_dates[date_str].append(t)

        # 4. Relato
        print("\n" + "="*80)
        print("📊 ANÁLISE DE DETECÇÃO DE DEPÓSITOS (últimos 30 dias)")
        print("="*80)

        undetected = []
        for date_str in sorted(deposit_dates.keys(), reverse=True):
            deps = deposit_dates[date_str]
            trades_count = len(trade_dates.get(date_str, []))
            
            status = "✅" if trades_count > 0 else "❌"
            print(f"\n{status} {date_str}: {len(deps)} depósito(s) → {trades_count} trade(s)")
            
            for d in deps:
                print(f"   - {d['created_at_utc']:%H:%M:%S} | "
                      f"{d['currency']} {d['amount']} | "
                      f"ledger_id={d['ledger_id'][:12]}...")
                if trades_count == 0:
                    undetected.append(d)
            
            if trades_count > 0:
                for t in trade_dates[date_str]:
                    print(f"   ✓ Trade {t['id']}: {t['side']} {t['size']} BTC @ {t['ts']:%H:%M:%S}")

        print("\n" + "="*80)
        if undetected:
            print(f"⚠️  DEPÓSITOS NÃO DETECTADOS: {len(undetected)}")
            for d in undetected:
                print(f"\n   ❌ {d['created_at_utc']:%Y-%m-%d %H:%M:%S} UTC")
                print(f"      Moeda: {d['currency']} | Valor: {d['amount']}")
                print(f"      Ledger ID: {d['ledger_id']}")
        else:
            print("✅ Todos os depósitos foram detectados!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    main()
