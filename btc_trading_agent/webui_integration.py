#!/usr/bin/env python3
"""
Bitcoin Trading Agent - Open WebUI Integration
Permite consultar e interagir com o agente via Open WebUI
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from flask import Flask, request, jsonify

# Adicionar paths
AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(AGENT_DIR.parent))

from kucoin_api import get_price_fast, get_orderbook, analyze_orderbook
from training_db import TrainingDatabase
from fast_model import FastTradingModel, MarketState

# ====================== CONFIGURAÇÃO ======================
OLLAMA_HOST = os.getenv("OLLAMA_HOST") or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"
WEBUI_HOST = os.getenv("OPENWEBUI_HOST") or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"
AGENT_API_PORT = int(os.getenv("AGENT_API_PORT", "8510"))

# ====================== CLIENTE DO AGENTE ======================
class TradingAgentClient:
    """Cliente para consultar dados do agente de trading"""
    
    def __init__(self):
        self.db = TrainingDatabase()
        self.model = FastTradingModel("BTC-USDT")
        self._cache = {}
        self._cache_time = 0
    
    def get_current_price(self) -> Optional[float]:
        """Obtém preço atual do BTC"""
        return get_price_fast("BTC-USDT", timeout=3)
    
    def get_market_analysis(self) -> Dict[str, Any]:
        """Análise completa do mercado atual"""
        price = self.get_current_price()
        if not price:
            return {"error": "Preço indisponível"}
        
        # Order book
        ob = analyze_orderbook("BTC-USDT")
        
        # Atualizar indicadores
        self.model.indicators.update(price)
        
        return {
            "price": price,
            "price_formatted": f"${price:,.2f}",
            "timestamp": datetime.now().isoformat(),
            "orderbook": {
                "bid_volume": ob.get("bid_volume", 0),
                "ask_volume": ob.get("ask_volume", 0),
                "imbalance": ob.get("imbalance", 0),
                "spread": ob.get("spread", 0)
            },
            "indicators": {
                "rsi": self.model.indicators.rsi(),
                "momentum": self.model.indicators.momentum(),
                "volatility": self.model.indicators.volatility(),
                "trend": self.model.indicators.trend()
            },
            "signal": self._get_current_signal(price)
        }
    
    def _get_current_signal(self, price: float) -> Dict[str, Any]:
        """Gera sinal atual do modelo"""
        try:
            ob = analyze_orderbook("BTC-USDT")
            
            state = MarketState(
                price=price,
                bid=ob.get("bid_volume", 0),
                ask=ob.get("ask_volume", 0),
                spread=ob.get("spread", 0),
                orderbook_imbalance=ob.get("imbalance", 0),
                trade_flow=0,
                volume_ratio=1,
                rsi=self.model.indicators.rsi(),
                momentum=self.model.indicators.momentum(),
                volatility=self.model.indicators.volatility(),
                trend=self.model.indicators.trend()
            )
            
            signal = self.model.predict(state)
            return {
                "action": signal.action,
                "confidence": signal.confidence,
                "reason": signal.reason
            }
        except Exception as e:
            return {"action": "HOLD", "confidence": 0, "reason": f"Erro: {e}"}
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Obtém trades recentes do banco (PostgreSQL)"""
        return self.db.get_recent_trades(limit=limit, include_dry=True)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Estatísticas de performance"""
        stats = self.db.calculate_performance("BTC-USDT")
        return stats
    
    def get_recent_decisions(self, limit: int = 20) -> List[Dict]:
        """Decisões recentes do modelo (PostgreSQL)"""
        return self.db.get_recent_decisions(limit=limit)
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Status geral do agente"""
        price = self.get_current_price()
        stats = self.get_performance_stats()
        
        return {
            "status": "online",
            "symbol": "BTC-USDT",
            "current_price": price,
            "price_formatted": f"${price:,.2f}" if price else "N/A",
            "performance": stats,
            "model_stats": self.model.get_stats(),
            "last_update": datetime.now().isoformat()
        }
    
    def format_status_message(self) -> str:
        """Formata status para resposta em texto"""
        status = self.get_agent_status()
        analysis = self.get_market_analysis()
        
        msg = f"""📊 **Status do Agente Bitcoin Trading**

💰 **Preço Atual:** {status.get('price_formatted', 'N/A')}

📈 **Indicadores:**
- RSI: {analysis['indicators']['rsi']:.1f}
- Momentum: {analysis['indicators']['momentum']:.4f}
- Volatilidade: {analysis['indicators']['volatility']:.4f}
- Tendência: {analysis['indicators']['trend']:.4f}

🎯 **Sinal Atual:** {analysis['signal']['action']}
- Confiança: {analysis['signal']['confidence']:.1%}
- Razão: {analysis['signal']['reason']}

📊 **Performance:**
- Total Trades: {status['performance'].get('total_trades', 0)}
- Win Rate: {status['performance'].get('win_rate', 0):.1%}
- PnL Total: ${status['performance'].get('total_pnl', 0):.2f}

⏰ Atualizado: {datetime.now().strftime('%H:%M:%S')}
"""
        return msg
    
    def answer_question(self, question: str) -> str:
        """Responde perguntas sobre o agente/mercado"""
        q = question.lower()
        
        # Preço
        if any(w in q for w in ["preço", "price", "cotação", "valor", "quanto"]):
            price = self.get_current_price()
            if price:
                return f"💰 O preço atual do Bitcoin é **${price:,.2f}**"
            return "❌ Não foi possível obter o preço atual"
        
        # Status
        if any(w in q for w in ["status", "como está", "situação"]):
            return self.format_status_message()
        
        # Trades
        if any(w in q for w in ["trade", "operação", "compra", "venda", "histórico"]):
            trades = self.get_recent_trades(5)
            if not trades:
                return "📭 Nenhum trade registrado ainda"
            
            msg = "📜 **Últimos Trades:**\n\n"
            for t in trades:
                side = "🟢 BUY" if t['side'] == 'buy' else "🔴 SELL"
                msg += f"- {side} {t['size']:.6f} BTC @ ${t['price']:,.2f}"
                if t.get('pnl'):
                    msg += f" (PnL: ${t['pnl']:.2f})"
                msg += f" - {t['created_at'][:16]}\n"
            return msg
        
        # Performance
        if any(w in q for w in ["performance", "lucro", "pnl", "resultado", "ganho"]):
            stats = self.get_performance_stats()
            return f"""📊 **Performance do Agente:**
- Total de Trades: {stats.get('total_trades', 0)}
- Trades Vencedores: {stats.get('winning_trades', 0)}
- Win Rate: {stats.get('win_rate', 0):.1%}
- PnL Total: ${stats.get('total_pnl', 0):.2f}
- Média por Trade: ${stats.get('avg_pnl', 0):.2f}
"""
        
        # Sinal/Decisão
        if any(w in q for w in ["sinal", "decisão", "recomendação", "devo", "comprar", "vender"]):
            analysis = self.get_market_analysis()
            signal = analysis['signal']
            
            emoji = "🟢" if signal['action'] == "BUY" else "🔴" if signal['action'] == "SELL" else "⚪"
            return f"""{emoji} **Sinal Atual: {signal['action']}**
- Confiança: {signal['confidence']:.1%}
- Razão: {signal['reason']}

⚠️ *Isso não é conselho financeiro. Faça sua própria análise.*
"""
        
        # Indicadores
        if any(w in q for w in ["indicador", "rsi", "momentum", "volatilidade", "técnico"]):
            analysis = self.get_market_analysis()
            ind = analysis['indicators']
            return f"""📈 **Indicadores Técnicos:**
- RSI: {ind['rsi']:.1f} {'(sobrecomprado)' if ind['rsi'] > 70 else '(sobrevendido)' if ind['rsi'] < 30 else '(neutro)'}
- Momentum: {ind['momentum']:.4f} {'(positivo)' if ind['momentum'] > 0 else '(negativo)'}
- Volatilidade: {ind['volatility']:.4f} {'(alta)' if ind['volatility'] > 0.02 else '(baixa)'}
- Tendência: {ind['trend']:.4f} {'(alta)' if ind['trend'] > 0 else '(baixa)'}
"""
        
        # Order book
        if any(w in q for w in ["order", "book", "livro", "oferta", "demanda"]):
            analysis = self.get_market_analysis()
            ob = analysis['orderbook']
            imb = ob['imbalance']
            return f"""📚 **Order Book BTC-USDT:**
- Volume Bid (compra): {ob['bid_volume']:.2f}
- Volume Ask (venda): {ob['ask_volume']:.2f}
- Desequilíbrio: {imb:.2%} {'(mais compradores)' if imb > 0 else '(mais vendedores)'}
- Spread: {ob['spread']:.2f}%
"""
        
        # Fallback - mostrar status geral
        return self.format_status_message()

# ====================== API FLASK ======================
app = Flask(__name__)
client = TradingAgentClient()

@app.route('/api/status', methods=['GET'])
def api_status():
    """Endpoint de status do agente"""
    return jsonify(client.get_agent_status())

@app.route('/api/price', methods=['GET'])
def api_price():
    """Preço atual"""
    price = client.get_current_price()
    return jsonify({
        "symbol": "BTC-USDT",
        "price": price,
        "formatted": f"${price:,.2f}" if price else None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/analysis', methods=['GET'])
def api_analysis():
    """Análise de mercado"""
    return jsonify(client.get_market_analysis())

@app.route('/api/trades', methods=['GET'])
def api_trades():
    """Trades recentes"""
    limit = request.args.get('limit', 10, type=int)
    return jsonify(client.get_recent_trades(limit))

@app.route('/api/performance', methods=['GET'])
def api_performance():
    """Performance do agente"""
    return jsonify(client.get_performance_stats())

@app.route('/api/ask', methods=['POST'])
def api_ask():
    """Endpoint para perguntas em linguagem natural"""
    data = request.get_json() or {}
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "Question required"}), 400
    
    answer = client.answer_question(question)
    return jsonify({
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Endpoint compatível com Open WebUI"""
    data = request.get_json() or {}
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({"error": "Messages required"}), 400
    
    # Pegar última mensagem do usuário
    user_msg = None
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            user_msg = msg.get('content', '')
            break
    
    if not user_msg:
        return jsonify({"error": "No user message found"}), 400
    
    # Gerar resposta
    answer = client.answer_question(user_msg)
    
    return jsonify({
        "model": "btc-trading-agent",
        "message": {
            "role": "assistant",
            "content": answer
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "healthy", "service": "btc-trading-agent"})

# ====================== OPEN WEBUI FUNCTION ======================
def btc_trading_agent_function(question: str) -> str:
    """
    Função para Open WebUI - Consulta o agente de trading Bitcoin
    
    Args:
        question: Pergunta sobre o mercado ou agente
        
    Returns:
        Resposta do agente
    """
    client = TradingAgentClient()
    return client.answer_question(question)

# ====================== OLLAMA INTEGRATION ======================
def register_with_ollama():
    """Registra função como tool no Ollama"""
    tool_definition = {
        "type": "function",
        "function": {
            "name": "btc_trading_agent",
            "description": "Consulta o agente de trading de Bitcoin. Use para obter preço atual, análise de mercado, indicadores técnicos, histórico de trades e sinais de compra/venda.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Pergunta sobre Bitcoin, mercado ou trading"
                    }
                },
                "required": ["question"]
            }
        }
    }
    return tool_definition

# ====================== OPENWEBUI TOOL MANIFEST ======================
OPENWEBUI_TOOL = {
    "id": "btc_trading_agent",
    "name": "Bitcoin Trading Agent",
    "description": "Consulta o agente de trading de Bitcoin 24/7",
    "icon": "₿",
    "endpoint": f"http://localhost:{AGENT_API_PORT}/api/ask",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body_template": '{"question": "{{input}}"}',
    "response_path": "answer"
}

# ====================== MAIN ======================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="BTC Trading Agent - WebUI Integration")
    parser.add_argument("--port", type=int, default=AGENT_API_PORT, help="API port")
    parser.add_argument("--host", default="0.0.0.0", help="API host")
    parser.add_argument("--test", action="store_true", help="Test mode")
    args = parser.parse_args()
    
    if args.test:
        # Testar funções
        print("🧪 Testando integração...\n")
        
        print("1️⃣ Preço atual:")
        print(client.answer_question("qual o preço do bitcoin"))
        print()
        
        print("2️⃣ Indicadores:")
        print(client.answer_question("mostre os indicadores"))
        print()
        
        print("3️⃣ Sinal:")
        print(client.answer_question("qual o sinal atual"))
        print()
        
        print("✅ Testes concluídos!")
        return
    
    print(f"""
╔═══════════════════════════════════════════════════════╗
║  Bitcoin Trading Agent - Open WebUI Integration       ║
╠═══════════════════════════════════════════════════════╣
║  API: http://{args.host}:{args.port}                          ║
║  Endpoints:                                           ║
║    GET  /api/status      - Status do agente           ║
║    GET  /api/price       - Preço atual                ║
║    GET  /api/analysis    - Análise de mercado         ║
║    GET  /api/trades      - Trades recentes            ║
║    GET  /api/performance - Performance                ║
║    POST /api/ask         - Perguntas em texto         ║
║    POST /api/chat        - Compatível com WebUI       ║
╚═══════════════════════════════════════════════════════╝
""")
    
    app.run(host=args.host, port=args.port, debug=False, threaded=True)

if __name__ == "__main__":
    main()
