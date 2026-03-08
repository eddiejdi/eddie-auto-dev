#!/usr/bin/env python3
"""
Script para trazer as negociações do agent autocoinbot do servidor
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# Connexão com o banco Postgres
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgress:shared_memory_2026@localhost:55432/autocoinbot'
)

def connect():
    """Conecta ao banco de dados"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Erro ao conectar ao banco: {e}")
        print(f"Database URL: {DATABASE_URL}")
        return None

def fetch_trades(limit=50, offset=0):
    """Busca trades do banco de dados"""
    conn = connect()
    if not conn:
        return None
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Tentar buscar da tabela de trades
        cur.execute("""
            SELECT 
                id, 
                timestamp, 
                symbol, 
                side, 
                price, 
                size, 
                funds,
                order_id,
                status,
                pnl,
                pnl_pct,
                dry_run,
                created_at,
                metadata
            FROM trades
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        trades = cur.fetchall()
        cur.close()
        conn.close()
        
        return [dict(row) for row in trades]
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar trades da tabela: {e}")
        
        # Tentar buscar informações sobre as tabelas disponíveis
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public'
            """)
            tables = cur.fetchall()
            print(f"\n📋 Tabelas disponíveis no banco:")
            for table in tables:
                print(f"  - {table[0]}")
            cur.close()
        except Exception as e2:
            print(f"Erro ao listar tabelas: {e2}")
        
        conn.close()
        return None

def fetch_from_sqlite():
    """Busca trades do banco SQLite local como fallback"""
    import sqlite3
    
    db_path = "/home/edenilson/shared-auto-dev/btc_trading_agent/data/trading_agent.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Banco SQLite não encontrado em {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM trades
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        
        trades = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        return trades
    
    except sqlite3.Error as e:
        print(f"❌ Erro ao buscar trades do SQLite: {e}")
        return None

def format_trades(trades):
    """Formata trades para exibição"""
    if not trades:
        print("❌ Nenhuma negociação encontrada")
        return
    
    print(f"\n{'='*100}")
    print(f"📊 NEGOCIAÇÕES DO AGENT AUTOCOINBOT - Total: {len(trades)}")
    print(f"{'='*100}\n")
    
    for i, trade in enumerate(trades, 1):
        # Emoji baseado no lado
        emoji = "🟢 BUY" if trade.get('side') == 'buy' else "🔴 SELL"
        
        # Data formatada
        timestamp = trade.get('timestamp') or trade.get('created_at')
        if isinstance(timestamp, str):
            date_str = timestamp[:19]
        else:
            date_str = datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Status
        status = trade.get('status', 'unknown')
        status_emoji = "✅" if status == 'executed' else "⏳" if status == 'pending' else "❌"
        
        # Modo
        dry_run = trade.get('dry_run')
        mode = "🧪 SIMULAÇÃO" if dry_run else "💰 REAL"
        
        # PnL
        pnl = trade.get('pnl')
        pnl_str = f"${pnl:.2f}" if pnl is not None else "N/A"
        pnl_pct = trade.get('pnl_pct')
        pnl_pct_str = f"({pnl_pct:.2f}%)" if pnl_pct is not None else ""
        
        # Conversões seguras
        try:
            price = float(trade.get('price') or 0)
            size = float(trade.get('size') or 0)
            funds = float(trade.get('funds') or 0)
        except (TypeError, ValueError):
            price = 0
            size = 0
            funds = 0
        
        print(f"{i}. {emoji} {status_emoji} {mode}")
        print(f"   ID: {trade.get('id')} | Order: {trade.get('order_id', 'N/A')}")
        print(f"   Data: {date_str}")
        print(f"   Preço: ${price:,.2f}")
        print(f"   Quantidade: {size:.6f} BTC")
        print(f"   Valor: ${funds:,.2f}")
        print(f"   PnL: {pnl_str} {pnl_pct_str}")
        print(f"   Símbolo: {trade.get('symbol', 'N/A')}")
        
        # Metadata se houver
        metadata = trade.get('metadata')
        if metadata:
            try:
                if isinstance(metadata, str):
                    meta_json = json.loads(metadata)
                else:
                    meta_json = metadata
                if meta_json:
                    print(f"   Meta: {meta_json}")
            except:
                pass
        
        print()

def print_summary(trades):
    """Imprime resumo das negociações"""
    if not trades:
        return
    
    buy_trades = [t for t in trades if t.get('side') == 'buy']
    sell_trades = [t for t in trades if t.get('side') == 'sell']
    
    total_bought = sum(float(t.get('funds') or 0) for t in buy_trades)
    total_sold = sum(float(t.get('funds') or 0) for t in sell_trades)
    total_pnl = sum(float(t.get('pnl') or 0) for t in trades if t.get('pnl') is not None)
    
    print(f"\n{'='*100}")
    print(f"📈 RESUMO DAS NEGOCIAÇÕES")
    print(f"{'='*100}")
    print(f"Total de operações: {len(trades)}")
    print(f"  - Compras (🟢): {len(buy_trades)} operações | ${total_bought:,.2f} USDT")
    print(f"  - Vendas (🔴): {len(sell_trades)} operações | ${total_sold:,.2f} USDT")
    print(f"\nPnL Total: ${total_pnl:,.2f}")
    print(f"{'='*100}\n")

def main():
    print("🤖 Buscando negociações do AutoCoinBot...\n")
    
    # Tentar PostgreSQL primeiro
    print("🔍 Tentando importar de PostgreSQL...")
    trades = fetch_trades()
    
    # Se falhar, tentar SQLite
    if trades is None:
        print("\n🔄 Tentando banco SQLite local como fallback...")
        trades = fetch_from_sqlite()
    
    # Se ainda não obtém, avisar
    if trades is None or len(trades) == 0:
        print("\n⚠️ Nenhuma negociação encontrada em nenhuma fonte")
        return 1
    
    # Formatar e exibir
    format_trades(trades)
    print_summary(trades)
    
    # Salvar em JSON também
    output_file = "/tmp/autocoinbot_trades.json"
    with open(output_file, 'w') as f:
        json.dump(trades, f, indent=2, default=str)
    print(f"✅ Dados salvos em: {output_file}")
    
    return 0

if __name__ == "__main__":
    exit(main())
