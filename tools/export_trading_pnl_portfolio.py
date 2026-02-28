#!/usr/bin/env python3
"""Exporta trades, PnL acumulado e posição (patrimônio) para CSV.

Uso:
  python3 tools/export_trading_pnl_portfolio.py --outdir exports --dry-run

Se `DATABASE_URL` estiver definido no ambiente, o script usará ele.
"""
import os
import sys
import argparse
import csv
import time
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None


def get_db_conn(dsn):
    if psycopg2 is None:
        raise RuntimeError("psycopg2 não está instalado no ambiente. Instale com pip install psycopg2-binary")
    return psycopg2.connect(dsn)


def query_trades(conn):
    # tenta seleção com colunas conhecidas; se falhar, retorna SELECT * limited
    q = (
        "SELECT COALESCE(to_timestamp(\"timestamp\"), created_at) AS created_at,"
        " COALESCE(symbol,'BTC-USDT') AS symbol, side, price, size, funds, pnl, pnl_pct, dry_run, status"
        " FROM btc.trades ORDER BY COALESCE(\"timestamp\", EXTRACT(EPOCH FROM created_at)) ASC"
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(q)
    except Exception:
        cur.execute('SELECT * FROM btc.trades ORDER BY id ASC LIMIT 1000')
    rows = cur.fetchall()
    cur.close()
    return rows


def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            # convert datetimes
            for k, v in r.items():
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
            w.writerow(r)


def compute_cumulative_pnl(rows):
    cum = 0.0
    out = []
    for r in rows:
        pnl = r.get('pnl') or 0.0
        try:
            pnl = float(pnl)
        except Exception:
            pnl = 0.0
        cum += pnl
        out.append({'created_at': r.get('created_at'), 'symbol': r.get('symbol'), 'pnl': pnl, 'cumulative_pnl': cum})
    return out


def compute_positions(rows):
    # position by symbol: sum(size for buy) - sum(size for sell)
    pos = {}
    for r in rows:
        sym = r.get('symbol') or 'UNKNOWN'
        side = (r.get('side') or '').lower()
        size = r.get('size') or 0.0
        try:
            size = float(size)
        except Exception:
            size = 0.0
        if sym not in pos:
            pos[sym] = 0.0
        if side == 'buy':
            pos[sym] += size
        elif side == 'sell':
            pos[sym] -= size
    rows_out = [{'symbol': s, 'position': p} for s,p in pos.items()]
    return rows_out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', help='DATABASE_URL (padrão: env DATABASE_URL)')
    p.add_argument('--outdir', default='exports', help='Diretório de saída')
    p.add_argument('--dry-run', action='store_true', help='Não conecta: só imprime queries')
    args = p.parse_args()

    dsn = args.db or os.environ.get('DATABASE_URL')
    if not dsn and not args.dry_run:
        print('DATABASE_URL não definido e --dry-run não especificado; abortando', file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    outdir = os.path.join(os.getcwd(), args.outdir)

    if args.dry_run:
        print('Dry-run: não será feita conexão. Exemplo de query usada:')
        print('SELECT COALESCE(to_timestamp("timestamp"), created_at) AS created_at, COALESCE(symbol,\'BTC-USDT\') AS symbol, side, price, size, funds, pnl, pnl_pct, dry_run, status FROM btc.trades ORDER BY COALESCE("timestamp", EXTRACT(EPOCH FROM created_at)) ASC')
        print('Saída esperada: CSV em', outdir)
        return

    conn = get_db_conn(dsn)
    try:
        rows = query_trades(conn)
    finally:
        conn.close()

    if not rows:
        print('Nenhum trade encontrado na tabela btc.trades')
        return

    # normalize fieldnames
    fieldnames = list(rows[0].keys())
    trades_path = os.path.join(outdir, f'trades_{timestamp}.csv')
    write_csv(trades_path, rows, fieldnames)

    pnl_rows = compute_cumulative_pnl(rows)
    pnl_fields = ['created_at', 'symbol', 'pnl', 'cumulative_pnl']
    pnl_path = os.path.join(outdir, f'pnl_{timestamp}.csv')
    write_csv(pnl_path, pnl_rows, pnl_fields)

    pos_rows = compute_positions(rows)
    pos_fields = ['symbol', 'position']
    pos_path = os.path.join(outdir, f'positions_{timestamp}.csv')
    write_csv(pos_path, pos_rows, pos_fields)

    print('Export completos:')
    print(' - Trades:', trades_path)
    print(' - PnL acumulado:', pnl_path)
    print(' - Posições (patrimônio/posição):', pos_path)


if __name__ == '__main__':
    main()
