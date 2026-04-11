#!/usr/bin/env python3
"""
Validação de operações de trading - Busca por operações perdidas
Compara: KuCoin API vs PostgreSQL vs Agent Logs
"""

import json
import logging
import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)
log = logging.getLogger("validate_trades")

RUNTIME_DIR = Path(os.environ.get("BTC_AGENT_DIR", "/home/homelab/myClaude/btc_trading_agent"))
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

try:
    import kucoin_api
    from secrets_helper import get_database_url
except ImportError as e:
    log.error(f"❌ Import error: {e}")
    sys.exit(1)

SCHEMA = "btc"


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL unavailable")
    return url


def _connect():
    return psycopg2.connect(_db_url())


def get_kucoin_trades(symbol: str = "BTC-USDT", limit: int = 100) -> List[Dict[str, Any]]:
    """Obtém ultimas operações da KuCoin API"""
    try:
        fills = kucoin_api.get_fills(symbol=symbol, limit=limit) or []
        log.info(f"✅ KuCoin API: {len(fills)} operações")
        return fills
    except Exception as e:
        log.error(f"❌ Error fetching KuCoin trades: {e}")
        return []


def get_db_trades(conn, days: int = 7) -> Dict[str, Dict[str, Any]]:
    """Obtém operações do banco de dados"""
    import time
    cutoff_ts = time.time() - (days * 86400)
    
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"""
            SELECT id, order_id, symbol, side, price, size, funds, timestamp, 
                   dry_run, metadata, profile
            FROM {SCHEMA}.trades
            WHERE timestamp > %s
            ORDER BY timestamp DESC
        """, (cutoff_ts,))
        
        trades = {}
        for row in cur.fetchall():
            order_id = str(row.get("order_id") or "").strip()
            if order_id:
                trades[order_id] = dict(row)
        
        log.info(f"✅ Database: {len(trades)} operações (últimos {days} dias)")
        return trades


def get_agent_logs_trades(days: int = 7) -> Dict[str, Dict[str, Any]]:
    """Extrai operações dos logs do agent (journalctl)"""
    trades = {}
    try:
        cmd = f"""
        journalctl -u crypto-agent@BTC_USDT_aggressive.service \\
                  -u crypto-agent@BTC_USDT_conservative.service \\
                  --since "{days} days ago" --no-pager --output=json 2>/dev/null | \\
        grep -o '"order_id":"[^"]*"' | cut -d'"' -f4 | sort -u
        """
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for order_id in result.stdout.strip().split('\n'):
                order_id = order_id.strip()
                if order_id:
                    trades[order_id] = {"source": "logs"}
        
        log.info(f"✅ Agent Logs: {len(trades)} operações encontradas")
    except Exception as e:
        log.warning(f"⚠️ Error parsing logs: {e}")
    
    return trades


def find_missing_trades() -> Dict[str, List[str]]:
    """Encontra operações perdidas comparando fontes"""
    
    log.info("\n" + "="*70)
    log.info("🔍 VALIDAÇÃO DE OPERAÇÕES")
    log.info("="*70 + "\n")
    
    # Coletar dados
    kucoin_trades = get_kucoin_trades(limit=100)
    
    with _connect() as conn:
        db_trades = get_db_trades(conn, days=7)
    
    agent_log_trades = get_agent_logs_trades(days=7)
    
    # Converter KuCoin para dict por order_id
    kucoin_by_id = {}
    for fill in kucoin_trades:
        order_id = str(fill.get("orderId") or "").strip()
        if order_id:
            kucoin_by_id[order_id] = fill
    
    # Comparar
    log.info("\n📊 ANÁLISE DE COBERTURA:\n")
    
    # KuCoin IDs
    kucoin_ids = set(kucoin_by_id.keys())
    db_ids = set(db_trades.keys())
    log_ids = set(agent_log_trades.keys())
    
    # Operações perdidas
    missing_in_db = kucoin_ids - db_ids
    missing_in_logs = kucoin_ids - log_ids
    in_logs_not_db = log_ids - db_ids
    in_db_not_kucoin = db_ids - kucoin_ids
    
    results = {
        "missing_in_db": list(missing_in_db),
        "missing_in_logs": list(missing_in_logs),
        "in_logs_not_db": list(in_logs_not_db),
        "in_db_not_kucoin": list(in_db_not_kucoin),
    }
    
    # Report
    log.info(f"📍 KuCoin API:     {len(kucoin_ids)} operações")
    log.info(f"📍 Base de Dados:  {len(db_ids)} operações")
    log.info(f"📍 Logs Agent:     {len(log_ids)} operações")
    
    if missing_in_db:
        log.warning(f"\n⚠️  PERDIDAS NO BD ({len(missing_in_db)}):")
        for order_id in missing_in_db:
            fill = kucoin_by_id[order_id]
            log.warning(f"   • {order_id[:12]}... | {fill.get('side').upper():4} "
                       f"{float(fill.get('size', 0)):12.8f} BTC @ ${float(fill.get('price', 0)):10.2f}")
    
    if in_logs_not_db:
        log.warning(f"\n⚠️  NOS LOGS MAS NÃO NO BD ({len(in_logs_not_db)}):")
        for order_id in list(in_logs_not_db)[:10]:
            log.warning(f"   • {order_id[:12]}...")
    
    if in_db_not_kucoin:
        log.info(f"\n✅ No BD mas não na KuCoin ({len(in_db_not_kucoin)}) - Operações antigas OK")
    
    # Validar conteúdo das operações sincronizadas
    log.info("\n" + "="*70)
    log.info("🔐 VALIDAÇÃO DE INTEGRIDADE")
    log.info("="*70 + "\n")
    
    mismatches = 0
    for order_id in kucoin_ids & db_ids:
        kucoin_trade = kucoin_by_id[order_id]
        db_trade = db_trades[order_id]
        
        kucoin_price = float(kucoin_trade.get("price", 0))
        db_price = float(db_trade.get("price", 0))
        kucoin_size = float(kucoin_trade.get("size", 0))
        db_size = float(db_trade.get("size", 0))
        
        # Validar com tolerância de 0.01%
        price_diff_pct = abs(kucoin_price - db_price) / kucoin_price * 100 if kucoin_price > 0 else 0
        size_diff_pct = abs(kucoin_size - db_size) / kucoin_size * 100 if kucoin_size > 0 else 0
        
        if price_diff_pct > 0.01 or size_diff_pct > 0.01:
            log.warning(f"⚠️  Mismatch {order_id[:12]}...: "
                       f"price_diff={price_diff_pct:.4f}%, size_diff={size_diff_pct:.4f}%")
            mismatches += 1
    
    if mismatches == 0:
        log.info("✅ Todas as operações sincronizadas têm dados íntegros!")
    else:
        log.warning(f"⚠️  {mismatches} operações com descrepâncias encontradas")
    
    # Summary
    log.info("\n" + "="*70)
    log.info("📋 SUMÁRIO")
    log.info("="*70 + "\n")
    
    total_missing = len(missing_in_db) + len(in_logs_not_db)
    if total_missing == 0:
        log.info("✅ PERFEITO! Nenhuma operação perdida detectada!")
    else:
        log.warning(f"⚠️  {total_missing} operações com potencial de sincronização incompleta")
    
    return results


def sync_missing_trades(missing_in_db: List[str], conn) -> int:
    """Sincroniza operações perdidas"""
    if not missing_in_db:
        log.info("✅ Nenhuma operação para sincronizar")
        return 0
    
    log.info(f"\n⏳ Sincronizando {len(missing_in_db)} operações perdidas...")
    
    kucoin_trades = get_kucoin_trades(limit=100)
    kucoin_by_id = {str(f.get("orderId") or ""): f for f in kucoin_trades}
    
    inserted = 0
    with conn.cursor() as cur:
        for order_id in missing_in_db:
            if order_id not in kucoin_by_id:
                continue
            
            fill = kucoin_by_id[order_id]
            
            try:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.trades
                        (symbol, side, price, size, funds, order_id, dry_run, 
                         timestamp, metadata, profile)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE, %s, %s, %s)
                    ON CONFLICT (order_id) DO NOTHING
                """, (
                    fill.get("symbol", "BTC-USDT"),
                    fill.get("side", "").lower(),
                    float(fill.get("price", 0)),
                    float(fill.get("size", 0)),
                    float(fill.get("funds", 0)),
                    order_id,
                    fill.get("createdAt") or fill.get("timestamp"),
                    json.dumps({"source": "recovery", "trade_id": fill.get("tradeId")}),
                    "recovery_sync",
                ))
                inserted += 1
                log.info(f"   ✅ {order_id[:12]}... sincronizado")
            except Exception as e:
                log.error(f"   ❌ {order_id[:12]}...: {e}")
    
    conn.commit()
    log.info(f"✅ {inserted} operações recuperadas!")
    return inserted


def main() -> int:
    try:
        results = find_missing_trades()
        
        # Se houver operações perdidas, tentar recuperar
        missing_in_db = results.get("missing_in_db", [])
        if missing_in_db:
            log.info("\n🔄 Tentando recuperar operações perdidas...\n")
            with _connect() as conn:
                sync_missing_trades(missing_in_db, conn)
        
        log.info("\n✅ Validação concluída!")
        return 0
    
    except Exception as e:
        log.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
