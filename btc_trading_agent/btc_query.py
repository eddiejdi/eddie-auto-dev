#!/usr/bin/env python3
"""
Bitcoin Trading Agent - Consulta Simples
Versão standalone sem dependências externas pesadas
"""

import os
import sys
import json
import psycopg2
import psycopg2.extras
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Paths
AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))

from kucoin_api import get_price_fast, analyze_orderbook

# ====================== DATABASE ======================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:shared_memory_2026@172.17.0.2:5432/postgres")
SCHEMA = "btc"

def get_db_connection():
    """Conexão com o banco de dados (PostgreSQL)"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro ao conectar PostgreSQL: {e}")
        return None

# ====================== FUNÇÕES DE CONSULTA ======================

def get_btc_price() -> str:
    """Obtém preço atual do Bitcoin"""
    price = get_price_fast("BTC-USDT", timeout=5)
    if price:
        return f"💰 Bitcoin: ${price:,.2f}"
    return "❌ Preço indisponível"

def get_market_analysis() -> str:
    """Análise de mercado"""
    price = get_price_fast("BTC-USDT", timeout=5)
    if not price:
        return "❌ Dados de mercado indisponíveis"
    
    ob = analyze_orderbook("BTC-USDT")
    
    # Importar indicadores se disponível
    try:
        from fast_model import FastTradingModel
        model = FastTradingModel("BTC-USDT")
        model.indicators.update(price)
        
        rsi = model.indicators.rsi()
        momentum = model.indicators.momentum()
        volatility = model.indicators.volatility()
        trend = model.indicators.trend()
    except:
        rsi = momentum = volatility = trend = 0
    
    imb = ob.get('imbalance', 0)
    
    return f"""📊 **Análise Bitcoin**

💰 **Preço:** ${price:,.2f}

📈 **Indicadores:**
- RSI: {rsi:.1f} {'(sobrecomprado)' if rsi > 70 else '(sobrevendido)' if rsi < 30 else '(neutro)'}
- Momentum: {momentum:.4f}
- Volatilidade: {volatility:.4f}
- Tendência: {trend:.4f}

📚 **Order Book:**
- Bid Volume: {ob.get('bid_volume', 0):.2f}
- Ask Volume: {ob.get('ask_volume', 0):.2f}
- Desequilíbrio: {imb:.2%} {'(compradores)' if imb > 0 else '(vendedores)'}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""

def get_trading_signal() -> str:
    """Sinal de trading atual"""
    try:
        from fast_model import FastTradingModel, MarketState
        
        price = get_price_fast("BTC-USDT", timeout=5)
        if not price:
            return "❌ Sinal indisponível"
        
        ob = analyze_orderboard("BTC-USDT")
        model = FastTradingModel("BTC-USDT")
        model.indicators.update(price)
        
        state = MarketState(
            price=price,
            bid=ob.get("bid_volume", 0),
            ask=ob.get("ask_volume", 0),
            spread=ob.get("spread", 0),
            orderbook_imbalance=ob.get("imbalance", 0),
            trade_flow=0,
            volume_ratio=1,
            rsi=model.indicators.rsi(),
            momentum=model.indicators.momentum(),
            volatility=model.indicators.volatility(),
            trend=model.indicators.trend()
        )
        
        signal = model.predict(state)
        
        emoji = "🟢" if signal.action == "BUY" else "🔴" if signal.action == "SELL" else "⚪"
        
        return f"""{emoji} **Sinal: {signal.action}**
- Confiança: {signal.confidence:.1%}
- Razão: {signal.reason}
- Preço: ${price:,.2f}

⚠️ *Isso não é conselho financeiro.*
"""
    except Exception as e:
        return f"❌ Erro ao gerar sinal: {e}"

def get_recent_trades(limit: int = 5) -> str:
    """Trades recentes"""
    conn = get_db_connection()
    if not conn:
        return "📭 Nenhum trade registrado (banco indisponível)"
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT * FROM btc.trades 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return "📭 Nenhum trade registrado"
        
        msg = "📜 **Trades Recentes:**\n\n"
        for t in trades:
            side = "🟢 BUY" if t['side'] == 'buy' else "🔴 SELL"
            msg += f"- {side} {t['size']:.6f} BTC @ ${t['price']:,.2f}"
            if t['pnl']:
                msg += f" (PnL: ${t['pnl']:.2f})"
            msg += f"\n  {t['created_at'][:16]}\n"
        
        return msg
    except Exception as e:
        return f"❌ Erro: {e}"

def get_performance() -> str:
    """Performance do agente"""
    conn = get_db_connection()
    if not conn:
        return "📊 Sem dados de performance (banco indisponível)"
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl
            FROM btc.trades 
            WHERE pnl IS NOT NULL
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        total = row['total'] or 0
        wins = row['wins'] or 0
        total_pnl = row['total_pnl'] or 0
        avg_pnl = row['avg_pnl'] or 0
        win_rate = wins / total if total > 0 else 0
        
        return f"""📊 **Performance do Agente:**

- Total de Trades: {total}
- Trades Vencedores: {wins}
- Win Rate: {win_rate:.1%}
- PnL Total: ${total_pnl:.2f}
- Média por Trade: ${avg_pnl:.2f}
"""
    except Exception as e:
        return f"❌ Erro: {e}"

def answer_question(question: str) -> str:
    """Responde perguntas sobre o agente/mercado"""
    q = question.lower()
    
    if any(w in q for w in ["preço", "price", "cotação", "valor", "quanto"]):
        return get_btc_price()
    
    if any(w in q for w in ["análise", "analysis", "indicador", "técnico", "rsi"]):
        return get_market_analysis()
    
    if any(w in q for w in ["sinal", "signal", "recomendação", "comprar", "vender"]):
        return get_trading_signal()
    
    if any(w in q for w in ["trade", "operação", "histórico"]):
        return get_recent_trades()
    
    if any(w in q for w in ["performance", "lucro", "pnl", "resultado"]):
        return get_performance()
    
    if any(w in q for w in ["status", "como está"]):
        price = get_btc_price()
        perf = get_performance()
        return f"{price}\n\n{perf}"
    
    # Default - mostrar tudo
    return get_market_analysis()

# ====================== CLI ======================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="BTC Trading Agent Query")
    parser.add_argument("query", nargs="?", default="status", help="Pergunta ou comando")
    parser.add_argument("--price", action="store_true", help="Mostrar preço")
    parser.add_argument("--analysis", action="store_true", help="Mostrar análise")
    parser.add_argument("--signal", action="store_true", help="Mostrar sinal")
    parser.add_argument("--trades", action="store_true", help="Mostrar trades")
    parser.add_argument("--performance", action="store_true", help="Mostrar performance")
    
    args = parser.parse_args()
    
    if args.price:
        print(get_btc_price())
    elif args.analysis:
        print(get_market_analysis())
    elif args.signal:
        print(get_trading_signal())
    elif args.trades:
        print(get_recent_trades())
    elif args.performance:
        print(get_performance())
    else:
        print(answer_question(args.query))

if __name__ == "__main__":
    main()
