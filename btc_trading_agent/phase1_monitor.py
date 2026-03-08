#!/usr/bin/env python3
"""
Phase 1 Monitoring Script - Ensemble Optimization Validation.

Monitora impacto das otimizações de ensemble na estratégia de trading:
- Win rate trajectory (target: 54.2% → 56-58%)
- Equity curve (target: $98 → $150+)
- Trade frequency (Phase 1 limit: 6/dia)
- Signal distribution (esperado: mais technical, menos noise)
- Drawdown analysis (max tolerance: 5%)

Data: 2026-03-05
Author: Copilot Agent
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================================
# CONFIGURATION
# ============================================================================

# DB credentials via Secrets Agent (sem hardcode)
try:
    from secrets_helper import get_database_url
    _DB_DSN = get_database_url()
except Exception:
    _DB_DSN = os.environ.get("DATABASE_URL", "")

# Compatibilidade com código que usa DB_CONFIG dict
from urllib.parse import urlparse as _urlparse
_parsed = _urlparse(_DB_DSN) if _DB_DSN else None
DB_CONFIG = {
    "host": _parsed.hostname if _parsed else "localhost",
    "port": _parsed.port if _parsed else 5433,
    "database": (_parsed.path or "/postgres").lstrip("/") if _parsed else "postgres",
    "user": _parsed.username if _parsed else "postgres",
    "password": _parsed.password if _parsed else "",
}

SYMBOL = "BTC-USDT"
PHASE_1_LIMIT = 6  # trades/day
PHASE_1_DURATION = 150  # Expected trades to validate
PHASE_2_THRESHOLD = 54.2  # Win rate % to escalate
DRAWDOWN_TOLERANCE = 5.0  # % max drawdown

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("phase1_monitor.log"),
    ],
)
logger = logging.getLogger(__name__)


# ============================================================================
# MONITORING FUNCTIONS
# ============================================================================


def get_db_connection() -> psycopg2.extensions.connection:
    """Connect to PostgreSQL database."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO btc, public")
    return conn


def get_baseline_metrics(conn: psycopg2.extensions.connection) -> dict[str, Any]:
    """
    Get baseline metrics from before deployment (2026-03-05 00:00).
    
    Comparação pré/pós otimização.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Baseline: trades antes das 08:42 de hoje (pré-restart)
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN side='buy' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END) as sell_count,
                ROUND(100.0 * SUM(CASE WHEN side='sell' AND pnl > 0 THEN 1 ELSE 0 END)::numeric 
                      / NULLIF(SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END), 0), 2) as win_rate_pct,
                ROUND(SUM(pnl)::numeric, 2) as total_pnl
            FROM btc.trades
            WHERE symbol=%s 
              AND created_at < (CURRENT_DATE + INTERVAL '8 hours 42 minutes')
            """,
            (SYMBOL,),
        )
        return dict(cur.fetchone() or {})


def get_current_metrics(
    conn: psycopg2.extensions.connection, hours: int = 24
) -> dict[str, Any]:
    """
    Get current metrics desde a otimização (últimas N horas).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Post-deployment metrics
        cur.execute(
            f"""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN side='buy' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END) as sell_count,
                ROUND(100.0 * SUM(CASE WHEN side='sell' AND pnl > 0 THEN 1 ELSE 0 END)::numeric 
                      / NULLIF(SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END), 0), 2) as win_rate_pct,
                ROUND(SUM(pnl)::numeric, 2) as total_pnl,
                ROUND(AVG(COALESCE((metadata->>'confidence')::numeric, 0))::numeric, 4) as avg_confidence,
                ROUND(AVG(CASE WHEN side='sell' THEN pnl ELSE NULL END)::numeric, 4) as avg_profit_per_sell,
                ROUND(MIN(CASE WHEN side='sell' THEN pnl ELSE NULL END)::numeric, 4) as min_profit_sell
            FROM btc.trades
            WHERE symbol=%s 
              AND created_at > NOW() - INTERVAL '{hours} hours'
            """,
            (SYMBOL,),
        )
        return dict(cur.fetchone() or {})


def get_daily_trades(
    conn: psycopg2.extensions.connection, days: int = 3
) -> dict[str, Any]:
    """
    Get daily trade frequency (validate Phase 1 limit).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT 
                DATE(created_at) as day,
                COUNT(*) as total_trades,
                SUM(CASE WHEN side='buy' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END) as sells,
                ROUND(100.0 * SUM(CASE WHEN side='sell' AND pnl > 0 THEN 1 ELSE 0 END)::numeric 
                      / NULLIF(SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END), 0), 2) as daily_wr
            FROM btc.trades
            WHERE symbol=%s 
              AND created_at > NOW() - INTERVAL '{days} days'
            GROUP BY DATE(created_at)
            ORDER BY day DESC
            """,
            (SYMBOL,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_signal_distribution(
    conn: psycopg2.extensions.connection,
) -> dict[str, float]:
    """
    Get signal distribution (validate ensemble weight impact).
    
    Esperado: mais technical, menos orderbook/flow noise.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                ROUND(100.0 * SUM(CASE WHEN (metadata->>'leading_signal')='technical' THEN 1 ELSE 0 END)::numeric 
                      / COUNT(*), 2) as technical_pct,
                ROUND(100.0 * SUM(CASE WHEN (metadata->>'leading_signal')='orderbook' THEN 1 ELSE 0 END)::numeric 
                      / COUNT(*), 2) as orderbook_pct,
                ROUND(100.0 * SUM(CASE WHEN (metadata->>'leading_signal')='flow' THEN 1 ELSE 0 END)::numeric 
                      / COUNT(*), 2) as flow_pct,
                ROUND(100.0 * SUM(CASE WHEN (metadata->>'leading_signal')='qlearning' THEN 1 ELSE 0 END)::numeric 
                      / COUNT(*), 2) as qlearning_pct
            FROM btc.trades
            WHERE symbol=%s 
              AND created_at > (CURRENT_DATE + INTERVAL '8 hours 42 minutes')
            """,
            (SYMBOL,),
        )
        row = cur.fetchone()
        return dict(row) if row else {}


def get_equity_curve(
    conn: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """
    Get equity curve trajectory (track drawdown).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH equity_track AS (
                SELECT 
                    created_at,
                    SUM(pnl) OVER (ORDER BY created_at) as cumulative_pnl,
                    MAX(SUM(pnl) OVER (ORDER BY created_at)) OVER () as max_equity,
                    ROUND(100.0 * (1.0 - NULLIF(
                        (MAX(SUM(pnl) OVER (ORDER BY created_at)) OVER () - 
                         SUM(pnl) OVER (ORDER BY created_at)) / 
                        NULLIF(MAX(SUM(pnl) OVER (ORDER BY created_at)) OVER (), 0), 0
                    ))::numeric, 2) as drawdown_pct
                FROM btc.trades
                WHERE symbol=%s 
                  AND created_at > (CURRENT_DATE + INTERVAL '8 hours 42 minutes')
                ORDER BY created_at
            )
            SELECT 
                created_at,
                ROUND(cumulative_pnl::numeric, 2) as equity,
                ROUND(drawdown_pct::numeric, 2) as drawdown_pct
            FROM equity_track
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (SYMBOL,),
        )
        return [dict(row) for row in cur.fetchall()]


def print_report(baseline: dict, current: dict, daily: list, signals: dict) -> None:
    """Print formatted monitoring report."""
    print("\n" + "=" * 80)
    print("📊 PHASE 1 MONITORING REPORT - Ensemble Optimization Impact")
    print("=" * 80)

    # Pre/Post comparison
    print("\n📈 WIN RATE EVOLUTION")
    print("-" * 80)
    baseline_wr = baseline.get("win_rate_pct", 0) or 0
    current_wr = current.get("win_rate_pct", 0) or 0
    wr_change = current_wr - baseline_wr if baseline_wr else 0
    arrow = "↑" if wr_change > 0 else "↓" if wr_change < 0 else "→"
    print(f"  Baseline (pre-opt)  : {baseline_wr:.2f}%")
    print(f"  Current (post-opt)  : {current_wr:.2f}% {arrow} {wr_change:+.2f}pp")
    print(f"  Target              : 56-58%")

    # Trade frequency
    print("\n🎯 DAILY TRADE FREQUENCY (Phase 1 Limit: 6/day)")
    print("-" * 80)
    for day_stat in daily[:3]:
        status = "✅" if day_stat["total_trades"] <= PHASE_1_LIMIT else "⚠️"
        print(
            f"  {day_stat['day']} {status} {day_stat['total_trades']} trades "
            f"({day_stat['buys']} BUY, {day_stat['sells']} SELL) - WR: {day_stat['daily_wr']}%"
        )

    # Signal distribution
    print("\n⚙️  ENSEMBLE SIGNAL DISTRIBUTION (post-deployment)")
    print("-" * 80)
    if signals:
        print(f"  Technical    : {signals.get('technical_pct', 0):.1f}% (↑ target)")
        print(f"  OrderBook    : {signals.get('orderbook_pct', 0):.1f}% (↓ noise reduction)")
        print(f"  Flow         : {signals.get('flow_pct', 0):.1f}% (↓ noise reduction)")
        print(f"  Q-Learning   : {signals.get('qlearning_pct', 0):.1f}% (↑ target)")
    else:
        print("  ⚠️  No decision data yet (trades in progress)")

    # PnL summary
    print("\n💰 P&L SUMMARY")
    print("-" * 80)
    baseline_pnl = baseline.get("total_pnl") or 0
    current_pnl = current.get("total_pnl") or 0
    print(f"  Baseline PnL        : ${baseline_pnl:.2f}")
    print(f"  Current PnL         : ${current_pnl:.2f}")
    print(f"  Change              : ${current_pnl - baseline_pnl:+.2f}")

    # Confidence analysis
    print("\n🔒 CONFIDENCE METRICS")
    print("-" * 80)
    avg_conf = current.get("avg_confidence") or 0
    print(f"  Avg Confidence      : {avg_conf:.4f} (min_threshold=0.48)")
    print(f"  Avg Profit/Sell     : ${current.get('avg_profit_per_sell') or 0:.4f}")
    print(f"  Min Profit (worst)  : ${current.get('min_profit_sell') or 0:.4f}")

    # Phase 2 readiness
    print("\n" + "=" * 80)
    print("📋 PHASE 2 READINESS CHECK")
    print("=" * 80)

    checks = []
    checks.append(
        (
            f"Win Rate > 54.2%",
            current_wr > PHASE_2_THRESHOLD if current_wr else False,
        )
    )
    checks.append(
        (
            f"Trades Count >= 50",
            (current.get("total_trades") or 0) >= 50,
        )
    )
    checks.append(
        (
            f"Daily Trades <= {PHASE_1_LIMIT}",
            all(day["total_trades"] <= PHASE_1_LIMIT for day in daily),
        )
    )
    checks.append((f"Uptrend (PnL positive)", current_pnl > 0))

    for check_name, passed in checks:
        status = "✅" if passed else "⏳"
        print(f"  {status} {check_name}")

    print("\n" + "=" * 80)
    logger.info(f"Report generated - WR: {current_wr:.2f}%, PnL: ${current_pnl:.2f}")


def main() -> None:
    """Main monitoring loop."""
    logger.info("Starting Phase 1 Monitoring...")
    logger.info(f"Config: {PHASE_1_LIMIT} trades/day, Target WR: {PHASE_2_THRESHOLD}%")

    try:
        conn = get_db_connection()
        logger.info("✅ Database connected")

        # Collect metrics
        baseline = get_baseline_metrics(conn)
        current = get_current_metrics(conn, hours=24)
        daily = get_daily_trades(conn, days=3)
        signals = get_signal_distribution(conn)

        # Print report
        print_report(baseline, current, daily, signals)

        # Save JSON snapshot
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "baseline": baseline,
            "current": current,
            "daily": daily,
            "signals": signals,
        }
        with open("phase1_snapshot.json", "w") as f:
            json.dump(snapshot, f, indent=2, default=str)
        logger.info("Snapshot saved to phase1_snapshot.json")

    except Exception as e:
        logger.error(f"Monitoring error: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
