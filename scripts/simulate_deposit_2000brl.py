#!/usr/bin/env python3
"""Simula um depósito de 2000 BRL no banco e testa se o agente o detecta."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import time

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from btc_trading_agent import secrets_helper


def main():
    """Insere depósito simulado e testa detecção."""
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

        # 1. Inserir depósito simulado de 2000 BRL
        now_ms = int(time.time() * 1000)
        
        print("\n" + "="*80)
        print("🔄 SIMULANDO DEPÓSITO DE 2000 BRL")
        print("="*80)
        
        cur.execute("""
            INSERT INTO btc.exchange_account_ledgers 
            (ledger_id, currency, amount, fee, balance, account_type, biz_type, 
             direction, created_at_ms, metadata)
            VALUES 
            (
                'sim_' || to_char(now(), 'YYYYMMDD_HHmmss'),
                'BRL',
                2000,
                0,
                0,
                'MAIN',
                'Fiat Deposit',
                'in',
                %s,
                '{}'::jsonb
            )
            RETURNING ledger_id, currency, amount, created_at_ms, account_type
        """, (now_ms,))
        
        result = cur.fetchone()
        if result:
            print(f"✅ Depósito inserido:")
            print(f"   Ledger ID: {result['ledger_id']}")
            print(f"   Moeda: {result['currency']}")
            print(f"   Valor: {result['amount']}")
            print(f"   Account: {result['account_type']}")
            print(f"   Timestamp: {result['created_at_ms']} ms")
        
        # 2. Verificar balance por conta
        print(f"\n📊 BALANCES ATUAIS (TRADE vs MAIN):")
        cur.execute("""
            SELECT 
                account_type,
                currency,
                SUM(amount) as total_in,
                COUNT(*) as tx_count
            FROM btc.exchange_account_ledgers
            WHERE currency IN ('BRL', 'BTC')
            GROUP BY account_type, currency
            ORDER BY account_type, currency
        """)
        
        for row in cur.fetchall():
            print(f"   {row['account_type']} / {row['currency']}: {row['total_in']} ({row['tx_count']} transações)")
        
        # 3. Procurar o depósito recém-inserido
        print(f"\n🔍 VERIFICANDO DETECÇÃO:")
        cur.execute("""
            SELECT 
                id, timestamp, side, size, order_id, metadata
            FROM btc.trades
            WHERE (metadata->>'source') = 'external_deposit'
            AND timestamp > %s - 60
            ORDER BY timestamp DESC
            LIMIT 5
        """, (time.time(),))
        
        recent_trades = cur.fetchall()
        if recent_trades:
            print(f"   ✅ Encontrados {len(recent_trades)} trades external_deposit recentes:")
            for t in recent_trades:
                print(f"      Trade {t['id']}: {t['side']} {t['size']} BTC @ {datetime.fromtimestamp(t['timestamp'], tz=timezone.utc)}")
        else:
            print(f"   ⚠️ Nenhum trade external_deposit detectado nos últimos 60 segundos")
            print(f"   Isso é normal se o agente não está rodando em tempo real.")
        
        print("\n" + "="*80)
        print("💡 PRÓXIMO PASSO: Dispare o agente para testar _detect_external_deposits()")
        print("="*80 + "\n")
        
        conn.close()

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
