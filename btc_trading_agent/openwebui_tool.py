"""
Bitcoin Trading Agent - Open WebUI Function/Tool
Copie este arquivo para a pasta de functions do Open WebUI
Ou use como referência para criar a tool na interface web
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any

# ====================== CONFIGURAÇÃO ======================
# Ajuste estes valores conforme sua instalação
AGENT_API_URL = os.getenv("BTC_AGENT_API", "http://localhost:8510")
AGENT_DIR = "/home/homelab/myClaude/btc_trading_agent"

class Tools:
    """
    Open WebUI Tools Class
    Define ferramentas que podem ser chamadas pelo LLM
    """
    
    def __init__(self):
        self.valves = self.Valves()
    
    class Valves:
        """Configurações da ferramenta"""
        def __init__(self):
            self.AGENT_API_URL = os.getenv("BTC_AGENT_API", "http://localhost:8510")
            self.TIMEOUT = 10
    
    def btc_price(self) -> str:
        """
        Obtém o preço atual do Bitcoin.
        
        :return: Preço atual do BTC em USD
        """
        try:
            # Tentar API local primeiro
            resp = requests.get(f"{self.valves.AGENT_API_URL}/api/price", timeout=5)
            if resp.ok:
                data = resp.json()
                return f"💰 Bitcoin: {data.get('formatted', 'N/A')}"
        except:
            pass
        
        # Fallback para API pública
        try:
            resp = requests.get(
                "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT",
                timeout=5
            )
            if resp.ok:
                price = float(resp.json()['data']['price'])
                return f"💰 Bitcoin: ${price:,.2f}"
        except Exception as e:
            return f"❌ Erro ao obter preço: {e}"
    
    def btc_analysis(self) -> str:
        """
        Análise técnica completa do Bitcoin incluindo RSI, momentum e tendência.
        
        :return: Análise técnica detalhada
        """
        try:
            resp = requests.get(
                f"{self.valves.AGENT_API_URL}/api/analysis",
                timeout=self.valves.TIMEOUT
            )
            if resp.ok:
                data = resp.json()
                ind = data.get('indicators', {})
                signal = data.get('signal', {})
                
                return f"""📊 **Análise Bitcoin**

💰 Preço: {data.get('price_formatted', 'N/A')}

📈 **Indicadores:**
- RSI: {ind.get('rsi', 0):.1f}
- Momentum: {ind.get('momentum', 0):.4f}
- Volatilidade: {ind.get('volatility', 0):.4f}
- Tendência: {ind.get('trend', 0):.4f}

🎯 **Sinal:** {signal.get('action', 'N/A')}
- Confiança: {signal.get('confidence', 0):.1%}
- Razão: {signal.get('reason', 'N/A')}
"""
            return "❌ Erro ao obter análise"
        except Exception as e:
            return f"❌ Erro: {e}"
    
    def btc_signal(self) -> str:
        """
        Obtém o sinal de trading atual (BUY/SELL/HOLD) do agente.
        
        :return: Sinal atual e confiança
        """
        try:
            resp = requests.get(
                f"{self.valves.AGENT_API_URL}/api/analysis",
                timeout=self.valves.TIMEOUT
            )
            if resp.ok:
                signal = resp.json().get('signal', {})
                action = signal.get('action', 'HOLD')
                conf = signal.get('confidence', 0)
                reason = signal.get('reason', '')
                
                emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
                
                return f"""{emoji} **Sinal: {action}**
Confiança: {conf:.1%}
Razão: {reason}

⚠️ *Isso não é conselho financeiro.*"""
            return "❌ Erro ao obter sinal"
        except Exception as e:
            return f"❌ Erro: {e}"
    
    def btc_trades(self, limit: int = 5) -> str:
        """
        Lista os trades recentes executados pelo agente.
        
        :param limit: Número de trades a retornar (padrão: 5)
        :return: Lista de trades recentes
        """
        try:
            resp = requests.get(
                f"{self.valves.AGENT_API_URL}/api/trades?limit={limit}",
                timeout=self.valves.TIMEOUT
            )
            if resp.ok:
                trades = resp.json()
                if not trades:
                    return "📭 Nenhum trade registrado"
                
                msg = "📜 **Trades Recentes:**\n\n"
                for t in trades:
                    side = "🟢 BUY" if t['side'] == 'buy' else "🔴 SELL"
                    msg += f"- {side} {t['size']:.6f} BTC @ ${t['price']:,.2f}"
                    if t.get('pnl'):
                        msg += f" (PnL: ${t['pnl']:.2f})"
                    msg += f"\n  {t['created_at'][:16]}\n"
                return msg
            return "❌ Erro ao obter trades"
        except Exception as e:
            return f"❌ Erro: {e}"
    
    def btc_performance(self) -> str:
        """
        Estatísticas de performance do agente de trading.
        
        :return: Métricas de performance
        """
        try:
            resp = requests.get(
                f"{self.valves.AGENT_API_URL}/api/performance",
                timeout=self.valves.TIMEOUT
            )
            if resp.ok:
                stats = resp.json()
                return f"""📊 **Performance do Agente:**

- Total de Trades: {stats.get('total_trades', 0)}
- Trades Vencedores: {stats.get('winning_trades', 0)}
- Win Rate: {stats.get('win_rate', 0):.1%}
- PnL Total: ${stats.get('total_pnl', 0):.2f}
- Média por Trade: ${stats.get('avg_pnl', 0):.2f}
"""
            return "❌ Erro ao obter performance"
        except Exception as e:
            return f"❌ Erro: {e}"
    
    def btc_ask(self, question: str) -> str:
        """
        Faz uma pergunta em linguagem natural sobre o Bitcoin ou o agente de trading.
        
        :param question: Pergunta sobre BTC, mercado, indicadores, etc.
        :return: Resposta do agente
        """
        try:
            resp = requests.post(
                f"{self.valves.AGENT_API_URL}/api/ask",
                json={"question": question},
                timeout=self.valves.TIMEOUT
            )
            if resp.ok:
                return resp.json().get('answer', 'Sem resposta')
            return "❌ Erro ao processar pergunta"
        except Exception as e:
            return f"❌ Erro: {e}"


# ====================== FUNCTION STANDALONE ======================
# Para uso fora do Open WebUI

def get_btc_info(query: str = "status") -> str:
    """
    Função standalone para obter informações do BTC
    
    Args:
        query: Tipo de consulta (price, analysis, signal, trades, performance, status)
    
    Returns:
        Informação solicitada
    """
    tools = Tools()
    
    q = query.lower()
    
    if "preço" in q or "price" in q or "cotação" in q:
        return tools.btc_price()
    elif "análise" in q or "analysis" in q or "indicador" in q:
        return tools.btc_analysis()
    elif "sinal" in q or "signal" in q or "comprar" in q or "vender" in q:
        return tools.btc_signal()
    elif "trade" in q or "operação" in q or "histórico" in q:
        return tools.btc_trades()
    elif "performance" in q or "lucro" in q or "resultado" in q:
        return tools.btc_performance()
    else:
        return tools.btc_ask(query)


# ====================== OPENWEBUI MANIFEST ======================
# Use isto para registrar a tool no Open WebUI

TOOL_MANIFEST = {
    "id": "btc_trading_agent",
    "name": "Bitcoin Trading Agent",
    "description": "Consulta o agente de trading de Bitcoin 24/7. Fornece preço atual, análise técnica, sinais de compra/venda, histórico de trades e performance.",
    "version": "1.0.0",
    "author": "Crypto",
    "icon": "₿",
    "tags": ["bitcoin", "trading", "crypto", "finance"],
    "tools": [
        {
            "name": "btc_price",
            "description": "Obtém o preço atual do Bitcoin",
            "parameters": {}
        },
        {
            "name": "btc_analysis",
            "description": "Análise técnica completa do Bitcoin",
            "parameters": {}
        },
        {
            "name": "btc_signal",
            "description": "Sinal de trading atual (BUY/SELL/HOLD)",
            "parameters": {}
        },
        {
            "name": "btc_trades",
            "description": "Lista trades recentes",
            "parameters": {
                "limit": {"type": "integer", "default": 5}
            }
        },
        {
            "name": "btc_performance",
            "description": "Estatísticas de performance",
            "parameters": {}
        },
        {
            "name": "btc_ask",
            "description": "Pergunta em linguagem natural",
            "parameters": {
                "question": {"type": "string", "required": True}
            }
        }
    ]
}


if __name__ == "__main__":
    # Teste rápido
    print("🧪 Testando ferramentas BTC...\n")
    
    tools = Tools()
    
    print("1️⃣ Preço:")
    print(tools.btc_price())
    print()
    
    print("2️⃣ Análise:")
    print(tools.btc_analysis())
    print()
    
    print("3️⃣ Sinal:")
    print(tools.btc_signal())
    print()
    
    print("✅ Testes concluídos!")
