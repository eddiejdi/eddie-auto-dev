#!/usr/bin/env python3
"""
Bitcoin Trading Agent - Relatorio Diario via WhatsApp
Envia resumo das ultimas 24 horas as 6:00 AM
"""

import os
import sys
import psycopg2
import psycopg2.extras
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:eddie_memory_2026@localhost:5432/postgres")
SCHEMA = "btc"

WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "96263ae8a9804541849ebc5efa212e0e")


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar config: {e}")
        return {}


def get_current_btc_price():
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("bitcoin", {}).get("usd")
    except:
        pass
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10
        )
        if response.status_code == 200:
            return float(response.json().get("price", 0))
    except:
        pass
    return None


def get_trades_last_24h():
    trades = []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        since = datetime.now() - timedelta(hours=24)
        cursor.execute(
            f"SELECT * FROM {SCHEMA}.trades WHERE timestamp > %s ORDER BY timestamp ASC",
            (since.timestamp(),)
        )
        trades = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao buscar trades: {e}")
    return trades


def get_model_stats():
    stats = {"episodes": 0, "reward": 0.0}
    try:
        import pickle
        model_file = os.path.join(MODELS_DIR, "qmodel_BTC_USDT.pkl")
        if os.path.exists(model_file):
            with open(model_file, "rb") as f:
                model_data = pickle.load(f)
                stats["episodes"] = model_data.get("episode", 0)
                stats["reward"] = model_data.get("reward", 0.0)
    except:
        pass
    return stats


def get_engine_status():
    try:
        response = requests.get("http://localhost:8511/api/status", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"engine": {"state": "offline"}}


def calculate_stats(trades):
    stats = {
        "total_trades": 0, "buys": 0, "sells": 0,
        "total_volume_usd": 0.0, "total_volume_btc": 0.0,
        "total_pnl": 0.0, "winning_trades": 0, "losing_trades": 0,
        "win_rate": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
        "avg_trade_size_usd": 0.0, "open_position": 0.0, "open_position_price": 0.0
    }
    if not trades:
        return stats
    
    stats["total_trades"] = len(trades)
    position = 0.0
    entry_price = 0.0
    
    for trade in trades:
        side = trade.get("side", "")
        price = trade.get("price", 0.0)
        size = trade.get("size", 0.0)
        funds = trade.get("funds", 0.0) or (price * size)
        pnl = trade.get("pnl", 0.0) or 0.0
        
        stats["total_volume_btc"] += size
        stats["total_volume_usd"] += funds if side == "buy" else (price * size)
        
        if side == "buy":
            stats["buys"] += 1
            position += size
            entry_price = price
        elif side == "sell":
            stats["sells"] += 1
            position -= size
            stats["total_pnl"] += pnl
            if pnl > 0:
                stats["winning_trades"] += 1
                stats["best_trade"] = max(stats["best_trade"], pnl)
            elif pnl < 0:
                stats["losing_trades"] += 1
                stats["worst_trade"] = min(stats["worst_trade"], pnl)
    
    stats["open_position"] = position
    stats["open_position_price"] = entry_price if position > 0 else 0
    if stats["sells"] > 0:
        stats["win_rate"] = (stats["winning_trades"] / stats["sells"]) * 100
    if stats["total_trades"] > 0:
        stats["avg_trade_size_usd"] = stats["total_volume_usd"] / stats["total_trades"]
    return stats


def format_daily_report(stats, model_stats, engine_status, current_price, config):
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    engine = engine_status.get("engine", {})
    state = engine.get("state", "offline")
    state_emoji = {"running": "🟢", "paused": "🟡", "stopped": "🔴", "offline": "⚫"}.get(state, "⚪")
    mode = "🧪 SIMULACAO" if config.get("dry_run", True) else "💰 MODO REAL"
    price_str = "${:,.2f}".format(current_price) if current_price else "N/A"
    
    pnl = stats["total_pnl"]
    pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
    
    if stats["open_position"] > 0:
        op = stats["open_position"]
        op_price = stats["open_position_price"]
        position_str = "🔵 {:.8f} BTC".format(op)
        if current_price and op_price > 0:
            unrealized = (current_price - op_price) * op
            unrealized_pct = ((current_price / op_price) - 1) * 100
            position_str += "\n├ Entrada: ${:,.2f}".format(op_price)
            position_str += "\n└ P&L nao realizado: ${:,.2f} ({:+.2f}%)".format(unrealized, unrealized_pct)
    else:
        position_str = "💤 Sem posicao aberta"
    
    report = """📊 *RELATORIO DIARIO - BITCOIN TRADING*
━━━━━━━━━━━━━━━━━━━━━

📅 *Periodo:* {} → {}
💵 *BTC/USD:* {}
{} *Engine:* {}
⚙️ *Modo:* {}

━━━━━━━━━━━━━━━━━━━━━
📈 *ESTATISTICAS (24h)*
━━━━━━━━━━━━━━━━━━━━━

*Trades:*
├ Total: {}
├ Compras: {} 🟢
├ Vendas: {} 🔴
└ Volume: ${:,.2f}

*Performance:*
├ {} PnL: ${:,.2f}
├ Win Rate: {:.1f}%
├ Melhor: ${:,.2f}
├ Pior: ${:,.2f}
└ Media/Trade: ${:,.2f}

*Posicao Atual:*
{}

━━━━━━━━━━━━━━━━━━━━━
🤖 *MODELO DE ML*
━━━━━━━━━━━━━━━━━━━━━
├ Episodios: {:,}
└ Reward: {:.4f}

━━━━━━━━━━━━━━━━━━━━━
🕐 Gerado em: {}
""".format(
        yesterday.strftime("%d/%m/%Y"), now.strftime("%d/%m/%Y"),
        price_str, state_emoji, state.upper(), mode,
        stats["total_trades"], stats["buys"], stats["sells"],
        stats["total_volume_usd"],
        pnl_emoji, pnl, stats["win_rate"],
        stats["best_trade"], stats["worst_trade"],
        stats["avg_trade_size_usd"],
        position_str,
        model_stats["episodes"], model_stats["reward"],
        now.strftime("%d/%m/%Y %H:%M:%S")
    )
    return report


def send_whatsapp_message(chat_id, message):
    if not chat_id:
        logger.warning("⚠️ WhatsApp chat_id nao configurado")
        return False
    try:
        url = "{}/api/sendText".format(WAHA_URL)
        headers = {"Content-Type": "application/json", "X-Api-Key": WAHA_API_KEY}
        payload = {"chatId": chat_id, "text": message, "session": WAHA_SESSION}
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            logger.info("✅ Relatorio enviado para {}".format(chat_id))
            return True
        else:
            logger.error("❌ WhatsApp erro: {} - {}".format(response.status_code, response.text))
            return False
    except Exception as e:
        logger.error("❌ WhatsApp excecao: {}".format(e))
        return False


def main():
    logger.info("📊 Gerando relatorio diario do Bitcoin Trading Agent...")
    
    config = load_config()
    chat_id = config.get("notifications", {}).get("whatsapp_chat_id", "")
    
    if not chat_id:
        logger.error("❌ WhatsApp chat_id nao configurado!")
        sys.exit(0)  # Nao falhar boot se chat_id ausente
    
    logger.info("📥 Coletando dados...")
    trades = get_trades_last_24h()
    stats = calculate_stats(trades)
    model_stats = get_model_stats()
    engine_status = get_engine_status()
    current_price = get_current_btc_price()
    
    logger.info("📝 Formatando relatorio...")
    report = format_daily_report(stats, model_stats, engine_status, current_price, config)
    
    print("\n" + "="*50)
    print(report)
    print("="*50 + "\n")
    
    logger.info("📤 Enviando para {}...".format(chat_id))
    success = send_whatsapp_message(chat_id, report)
    
    if success:
        logger.info("✅ Relatorio diario enviado com sucesso!")
    else:
        logger.error("❌ Falha ao enviar relatorio!")
        sys.exit(0)  # Nao falhar boot se envio falhar


if __name__ == "__main__":
    main()
