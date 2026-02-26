#!/usr/bin/env python3
"""
Bitcoin Trading Agent - Integração Telegram
Conecta o bot Telegram ao trading agent via Engine API HTTP (porta 8511)
Suporta: status, trades, performance, sinal e perguntas em linguagem natural
"""

import os
import httpx
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
HOMELAB_HOST = os.environ.get("HOMELAB_HOST", "192.168.15.2")
ENGINE_API_URL = os.environ.get("BTC_ENGINE_API_URL", f"http://{HOMELAB_HOST}:8511")
API_TIMEOUT = 5.0

# Comandos disponíveis
TRADING_COMMANDS = ["/btc", "/trades", "/performance", "/signal", "/trading"]


class TelegramTradingClient:
    """Cliente para consultar o trading agent via Engine API"""

    def __init__(self, base_url: str = ENGINE_API_URL):
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> Optional[dict]:
        """GET request à Engine API"""
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                resp = await client.get(f"{self.base_url}{path}")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            logger.warning(f"Trading API offline: {self.base_url}")
            return None
        except Exception as e:
            logger.error(f"Trading API error: {e}")
            return None

    async def get_status(self) -> str:
        """Status completo: preço, posição, PnL, sinal, modo"""
        status = await self._get("/api/status")
        if not status:
            return "⚠️ *Trading Agent offline*\n\nA API do trading agent não está respondendo."

        engine = status.get("engine", {})
        config = status.get("config", {})

        # Extrair dados
        symbol = config.get("symbol", "BTC-USDT")
        is_live = not config.get("dry_run", True)
        mode_emoji = "🔴 LIVE" if is_live else "🟡 DRY RUN"

        # Preço atual
        price_data = await self._get("/api/price")
        price = price_data.get("price", 0) if price_data else 0
        price_fmt = f"${price:,.2f}" if price else "N/A"

        # Posição
        position = engine.get("current_position", engine.get("position", 0))
        entry_price = engine.get("entry_price", 0)
        position_value = position * price if position and price else 0

        # PnL
        total_pnl = engine.get("total_pnl", 0)
        unrealized_pnl = (price - entry_price) * position if position and entry_price and price else 0
        pnl_pct = ((price / entry_price) - 1) * 100 if entry_price and price else 0

        # Sinal
        signals = await self._get("/api/signals")
        last_signal = signals.get("last_signal", {}) if signals else {}
        signal_action = last_signal.get("action", "N/A") if isinstance(last_signal, dict) else str(last_signal) if last_signal else "N/A"
        signal_conf = last_signal.get("confidence", 0) if isinstance(last_signal, dict) else 0

        signal_emoji = "🟢" if signal_action == "BUY" else "🔴" if signal_action == "SELL" else "⚪"

        # Stats
        total_trades = engine.get("total_trades", 0)
        winning_trades = engine.get("winning_trades", 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Uptime
        cycles = engine.get("cycles", engine.get("total_cycles", 0))

        # Saldos
        balances = await self._get("/api/balances")
        total_usdt = balances.get("formatted_total", "N/A") if balances else "N/A"

        msg = f"""🤖 *BTC Trading Agent*
━━━━━━━━━━━━━━━━━━━━

💰 *Preço:* {price_fmt}
⚡ *Modo:* {mode_emoji}

📊 *Posição:*"""

        if position and position > 0:
            pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
            msg += f"""
• {position:.8f} BTC (${position_value:,.2f})
• Entrada: ${entry_price:,.2f}
• {pnl_emoji} PnL aberto: ${unrealized_pnl:,.2f} ({pnl_pct:+.2f}%)"""
        else:
            msg += "\n• Sem posição aberta"

        msg += f"""

{signal_emoji} *Sinal:* {signal_action}"""
        if signal_conf:
            msg += f" ({signal_conf:.1%})"

        msg += f"""

📈 *Estatísticas:*
• Trades: {total_trades} | Win Rate: {win_rate:.0f}%
• PnL realizado: ${total_pnl:,.2f}
• Carteira: {total_usdt}
• Ciclos: {cycles:,}

⏰ {datetime.now().strftime('%d/%m %H:%M:%S')}"""

        return msg

    async def get_trades(self, limit: int = 5) -> str:
        """Últimos trades executados"""
        data = await self._get(f"/api/trades?limit={limit}")
        if not data:
            return "⚠️ *Trading Agent offline*\n\nA API do trading agent não está respondendo."

        trades_text = data.get("trades", "")

        # Se o endpoint retorna texto formatado do btc_query.py
        if isinstance(trades_text, str) and trades_text:
            return f"📜 *Últimos Trades*\n━━━━━━━━━━━━━━━━━━━━\n\n{trades_text}"

        # Se retorna lista de dicts
        if isinstance(trades_text, list):
            if not trades_text:
                return "📭 Nenhum trade registrado"

            msg = "📜 *Últimos Trades*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for t in trades_text[:limit]:
                side = "🟢 BUY" if t.get("side") == "buy" else "🔴 SELL"
                price = t.get("price", 0)
                size = t.get("size", 0)
                pnl = t.get("pnl")
                created = t.get("created_at", "")[:16]

                msg += f"{side} {size:.6f} BTC @ ${price:,.2f}"
                if pnl is not None:
                    pnl_emoji = "✅" if pnl >= 0 else "❌"
                    msg += f" → {pnl_emoji} ${pnl:,.2f}"
                msg += f"\n  _{created}_\n\n"

            return msg

        return "📭 Nenhum trade registrado"

    async def get_performance(self) -> str:
        """Estatísticas de performance"""
        data = await self._get("/api/performance")
        if not data:
            return "⚠️ *Trading Agent offline*\n\nA API do trading agent não está respondendo."

        perf = data.get("performance", "")

        # Se retorna texto formatado
        if isinstance(perf, str) and perf:
            return f"📊 *Performance*\n━━━━━━━━━━━━━━━━━━━━\n\n{perf}"

        # Se retorna dict
        if isinstance(perf, dict):
            total = perf.get("total_trades", 0)
            wins = perf.get("wins", 0)
            total_pnl = perf.get("total_pnl", 0)
            avg_pnl = perf.get("avg_pnl", 0)
            win_rate = (wins / total * 100) if total > 0 else 0

            return f"""📊 *Performance do Agente*
━━━━━━━━━━━━━━━━━━━━

• Total de Trades: {total}
• Trades Vencedores: {wins}
• Win Rate: {win_rate:.1f}%
• PnL Total: ${total_pnl:,.2f}
• Média por Trade: ${avg_pnl:,.2f}

⏰ {datetime.now().strftime('%d/%m %H:%M:%S')}"""

        return "📊 Sem dados de performance disponíveis"

    async def get_signal(self) -> str:
        """Sinal atual com confiança"""
        # Buscar sinal + análise de mercado
        signals = await self._get("/api/signals")
        analysis = await self._get("/api/analysis")

        if not signals:
            return "⚠️ *Trading Agent offline*\n\nA API do trading agent não está respondendo."

        last_signal = signals.get("last_signal", {})
        total_signals = signals.get("signals_generated", 0)

        if isinstance(last_signal, dict) and last_signal:
            action = last_signal.get("action", "N/A")
            confidence = last_signal.get("confidence", 0)
            reason = last_signal.get("reason", "")
            price = last_signal.get("price", 0)

            emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"

            msg = f"""{emoji} *Sinal: {action}*
━━━━━━━━━━━━━━━━━━━━

• Confiança: {confidence:.1%}
• Preço: ${price:,.2f}
• Razão: {reason}
• Sinais gerados: {total_signals:,}"""
        else:
            msg = f"""⚪ *Sinal: N/A*
━━━━━━━━━━━━━━━━━━━━

• Último sinal: {last_signal or 'Nenhum'}
• Sinais gerados: {total_signals:,}"""

        # Adicionar análise de mercado se disponível
        if analysis:
            analysis_text = analysis.get("analysis", "")
            if analysis_text:
                msg += f"\n\n📈 *Análise:*\n{analysis_text}"

        msg += f"\n\n⚠️ _Isso não é conselho financeiro._"
        return msg

    async def ask_question(self, question: str) -> str:
        """Pergunta em linguagem natural sobre o trading agent"""
        q = question.lower()

        # Roteamento baseado em keywords
        if any(w in q for w in ["preço", "price", "cotação", "valor", "quanto"]):
            price_data = await self._get("/api/price")
            if price_data and price_data.get("price"):
                return f"💰 Bitcoin: ${price_data['price']:,.2f}"
            return "❌ Preço indisponível"

        if any(w in q for w in ["lucro", "profit", "pnl", "ganhando", "perdendo",
                                "lucrando", "resultado"]):
            return await self.get_status()

        if any(w in q for w in ["sinal", "signal", "comprar", "vender",
                                "recomendação", "devo"]):
            return await self.get_signal()

        if any(w in q for w in ["trade", "operação", "operações", "histórico",
                                "últimos", "recentes"]):
            return await self.get_trades()

        if any(w in q for w in ["performance", "desempenho", "win rate",
                                "taxa", "estatística"]):
            return await self.get_performance()

        if any(w in q for w in ["saldo", "balance", "carteira", "wallet",
                                "quanto tenho"]):
            balances = await self._get("/api/balances")
            if balances:
                total = balances.get("formatted_total", "N/A")
                actives = balances.get("balances", [])
                msg = f"💼 *Saldo da Carteira:* {total}\n\n"
                for b in actives:
                    curr = b.get("currency", "?")
                    amt = b.get("balance", 0)
                    if curr == "BTC":
                        msg += f"• {curr}: {amt:.8f}\n"
                    else:
                        msg += f"• {curr}: {amt:.2f}\n"
                return msg
            return "❌ Saldos indisponíveis"

        if any(w in q for w in ["análise", "analysis", "indicador", "rsi",
                                "momentum", "mercado"]):
            analysis = await self._get("/api/analysis")
            if analysis:
                return analysis.get("analysis", "❌ Análise indisponível")
            return "❌ Análise indisponível"

        if any(w in q for w in ["status", "como está", "como vai", "situação"]):
            return await self.get_status()

        # Default: status completo
        return await self.get_status()

    async def get_balances(self) -> str:
        """Saldo da carteira KuCoin"""
        data = await self._get("/api/balances")
        if not data:
            return "⚠️ *Trading Agent offline*"

        total = data.get("formatted_total", "N/A")
        actives = data.get("balances", [])

        msg = f"""💼 *Saldo KuCoin*
━━━━━━━━━━━━━━━━━━━━
💰 *Total:* {total}

"""
        for b in actives:
            curr = b.get("currency", "?")
            amt = b.get("balance", 0)
            if curr == "BTC":
                msg += f"• *{curr}:* {amt:.8f}\n"
            else:
                msg += f"• *{curr}:* {amt:.2f}\n"

        msg += f"\n⏰ {datetime.now().strftime('%d/%m %H:%M:%S')}"
        return msg


def get_trading_help() -> str:
    """Texto de ajuda para comandos de trading"""
    return """*📈 Trading (BTC):*
/btc - Status completo do agent
/trades - Últimos trades executados
/performance - Win rate, PnL, estatísticas
/signal - Sinal atual (BUY/SELL/HOLD)
/trading [pergunta] - Perguntas livres

_Exemplos:_
`/trading está em lucro?`
`/trading qual o preço do BTC?`
`/trading quantos trades hoje?`"""
