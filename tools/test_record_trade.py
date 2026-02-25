#!/usr/bin/env python3
import logging
import json
from btc_trading_agent.training_db import TrainingDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

if __name__ == '__main__':
    db = TrainingDatabase()
    print(f"Using DB: {db.db_path}")
    trade_id = db.record_trade(
        symbol='TEST-BTC',
        side='buy',
        price=123.45,
        size=0.001,
        funds=0.123,
        order_id='test-order-001',
        dry_run=False,
        metadata={'note': 'integration-test'}
    )
    print('Inserted trade_id:', trade_id)
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM trades WHERE dry_run=0')
        count = cur.fetchone()[0]
    print('Count of dry_run=0 trades:', count)
