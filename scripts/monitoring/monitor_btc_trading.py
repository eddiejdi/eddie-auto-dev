#!/usr/bin/env python3
"""
Monitor e Alertas - BTC Trading Agent
Análise contínua de métricas críticas com alertas automáticos
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

class BTCTradingMonitor:
    def __init__(self, db_path="/home/homelab/myClaude/btc_trading_agent/data/trading_agent.db",
                 config_path="/home/homelab/myClaude/btc_trading_agent/config.json"):
        self.db_path = db_path
        self.config_path = config_path
        
    def get_metrics(self, hours=24):
        """Get trading metrics for last N hours"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        ts_cutoff = f"(strftime('%s', 'now') - {hours * 3600})"
        
        # Total trades & win rate
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MIN(pnl) as worst_pnl,
                MAX(pnl) as best_pnl
            FROM trades
            WHERE timestamp > {ts_cutoff}
        """)
        
        row = cur.fetchone()
        total_trades = row[0] or 0
        winning_trades = row[1] or 0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'hours': hours,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate_pct': round(win_rate, 2),
            'total_pnl': round(row[2] or 0, 2),
            'avg_pnl': round(row[3] or 0, 4),
            'worst_pnl': round(row[4] or 0, 4),
            'best_pnl': round(row[5] or 0, 4),
        }
        
        # Per-symbol breakdown
        cur.execute(f"""
            SELECT 
                symbol,
                COUNT(*) as count,
                SUM(pnl) as total_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_pct
            FROM trades
            WHERE timestamp > {ts_cutoff}
            GROUP BY symbol
            ORDER BY total_pnl
        """)
        
        metrics['by_symbol'] = {}
        for row in cur:
            metrics['by_symbol'][row[0]] = {
                'count': row[1],
                'pnl': round(row[2], 2),
                'win_rate': round(row[3], 1)
            }
        
        conn.close()
        return metrics
    
    def check_alerts(self):
        """Check for alert conditions"""
        metrics = self.get_metrics(24)
        alerts = []
        
        # Alert 1: Win Rate too low
        if metrics['total_trades'] >= 10 and metrics['win_rate_pct'] < 40:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"🚨 Win Rate CRITICAL: {metrics['win_rate_pct']}% (need >55%)"
            })
        
        # Alert 2: Daily loss exceeded
        if metrics['total_pnl'] < -50:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"🚨 Daily Loss CRITICAL: ${metrics['total_pnl']} (limit: -$150)"
            })
        
        # Alert 3: No trades in last hour
        recent = self.get_metrics(1)
        if recent['total_trades'] == 0:
            alerts.append({
                'level': 'WARNING',
                'message': "⚠️ No trades in last hour - check bot health"
            })
        
        # Alert 4: Symbol performing poorly
        with open(self.config_path) as f:
            config = json.load(f)
        
        for symbol, data in metrics['by_symbol'].items():
            if data['count'] >= 5 and data['win_rate'] < 25:
                alerts.append({
                    'level': 'WARNING',
                    'message': f"⚠️ {symbol}: Win Rate {data['win_rate']}% (only {data['count']} trades, PnL: ${data['pnl']})"
                })
        
        return alerts, metrics
    
    def print_report(self):
        """Print formatted report"""
        alerts, metrics = self.check_alerts()
        
        print("=" * 100)
        print(f"📊 BTC TRADING AGENT MONITOR - {metrics['timestamp']}")
        print("=" * 100)
        
        print(f"\n📈 OVERALL METRICS (Last {metrics['hours']}h):")
        print(f"  Trades: {metrics['total_trades']} (Winners: {metrics['winning_trades']})")
        print(f"  Win Rate: {metrics['win_rate_pct']}% {'✓' if metrics['win_rate_pct'] > 50 else '❌'}")
        print(f"  PnL Total: ${metrics['total_pnl']} {'✓' if metrics['total_pnl'] > 0 else '❌'}")
        print(f"  PnL Avg: ${metrics['avg_pnl']}")
        print(f"  Range: ${metrics['worst_pnl']} → ${metrics['best_pnl']}")
        
        print(f"\n📋 BY SYMBOL:")
        for symbol, data in sorted(metrics['by_symbol'].items(), key=lambda x: x[1]['pnl']):
            status = '✓' if data['pnl'] > 0 else '❌'
            print(f"  {symbol:10s} | Count: {data['count']:2d} | PnL: ${data['pnl']:8.2f} {status} | Win%: {data['win_rate']:5.1f}%")
        
        if alerts:
            print(f"\n🚨 ALERTS ({len(alerts)} total):")
            for alert in alerts:
                print(f"  [{alert['level']}] {alert['message']}")
        else:
            print(f"\n✅ No alerts")
        
        print("\n" + "=" * 100)


if __name__ == "__main__":
    monitor = BTCTradingMonitor()
    
    # Print report
    monitor.print_report()
    
    # Option: continuous monitoring
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("\n⏱️  Watching every 5 minutes (press Ctrl+C to stop)...")
        try:
            while True:
                time.sleep(300)  # 5 minutes
                monitor.print_report()
        except KeyboardInterrupt:
            print("\n✅ Monitoring stopped")
