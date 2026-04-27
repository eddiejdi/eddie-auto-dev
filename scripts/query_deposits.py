#!/usr/bin/env python3
import os, json, sys

out = {"connected": False, "error": None, "fiat_deposits": [], "external_deposit_trades": []}
# Prefer DATABASE_URL from Agent Secrets via helpers in the btc_trading_agent
DB_URL = None
try:
    # Import the project's secrets_helper to resolve DATABASE_URL via Secrets Agent
    from btc_trading_agent import secrets_helper as _sh
    DB_URL = _sh.get_database_url()
except Exception:
    # Fallback to env var or cron default if Secrets Agent resolution fails
    DB_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:eddie_memory_2026@127.0.0.1:5433/btc_trading"

try:
    import psycopg2
    import psycopg2.extras
except Exception as e:
    out["error"] = f"psycopg2 import error: {e}"
    print(json.dumps(out))
    sys.exit(0)

try:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "SELECT ledger_id,currency,amount,fee,balance,account_type,biz_type,direction,created_at_ms "
            "FROM btc.exchange_account_ledgers WHERE biz_type = %s ORDER BY created_at_ms DESC LIMIT 20",
            ("Fiat Deposit",),
        )
        out["fiat_deposits"] = cur.fetchall()
    except Exception as exc:
        out["error_fiat_deposits"] = str(exc)
    try:
        cur.execute(
            "SELECT id,to_timestamp(timestamp)::timestamptz AS ts,side,size,order_id,metadata "
            "FROM btc.trades WHERE (metadata->>'source') = %s ORDER BY timestamp DESC LIMIT 20",
            ("external_deposit",),
        )
        out["external_deposit_trades"] = cur.fetchall()
    except Exception as exc:
        out["error_external_trades"] = str(exc)
    out["connected"] = True
    cur.close()
    conn.close()
except Exception as e:
    out["error"] = str(e)

print(json.dumps(out, default=str))
