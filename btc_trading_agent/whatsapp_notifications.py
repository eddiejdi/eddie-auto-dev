#!/usr/bin/env python3
"""
Bitcoin Trading Engine - Notificações WhatsApp
Envia notificações de trades via WAHA API
"""

import os
import requests
import logging
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Carregar .env
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Configurações
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "96263ae8a9804541849ebc5efa212e0e")
NOTIFICATION_CHAT = os.getenv(
    "BTC_NOTIFICATION_CHAT", "5511981193899@c.us"
)  # Chat padrão

logger = logging.getLogger(__name__)


@dataclass
class TradeNotification:
    """Dados de uma notificação de trade"""

    side: str  # "buy" ou "sell"
    symbol: str
    size: float
    price: float
    funds: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    trade_type: str = "auto"  # auto, manual, stop_loss, take_profit
    dry_run: bool = True
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


def send_whatsapp_message(chat_id: str, message: str) -> bool:
    """
    Envia mensagem via WAHA API

    Args:
        chat_id: ID do chat (ex: "5511999999999@c.us" ou "grupo-id@g.us")
        message: Texto da mensagem

    Returns:
        True se enviou com sucesso
    """
    if not chat_id:
        logger.warning("⚠️ WhatsApp chat_id não configurado")
        return False

    try:
        url = f"{WAHA_URL}/api/sendText"
        headers = {"Content-Type": "application/json", "X-Api-Key": WAHA_API_KEY}
        payload = {"chatId": chat_id, "text": message, "session": WAHA_SESSION}

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200 or response.status_code == 201:
            logger.info(f"✅ WhatsApp: Mensagem enviada para {chat_id}")
            return True
        else:
            logger.error(f"❌ WhatsApp erro: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ WhatsApp exceção: {e}")
        return False


def format_trade_message(notification: TradeNotification) -> str:
    """
    Formata mensagem de trade para WhatsApp

    Args:
        notification: Dados do trade

    Returns:
        Mensagem formatada
    """
    # Emoji baseado no tipo
    if notification.side == "buy":
        emoji = "🟢"
        action = "COMPRA"
    else:
        emoji = "🔴"
        action = "VENDA"

    # Tipo de trade
    type_labels = {
        "auto": "🤖 Auto",
        "manual": "👤 Manual",
        "stop_loss": "🛑 Stop Loss",
        "take_profit": "🎯 Take Profit",
    }
    trade_type_str = type_labels.get(notification.trade_type, notification.trade_type)

    # Modo
    mode = "🧪 SIMULAÇÃO" if notification.dry_run else "💰 REAL"

    # Montar mensagem
    lines = [
        f"{emoji} *{action} DE BITCOIN* {emoji}",
        "",
        "📊 *Detalhes:*",
        f"├ Par: {notification.symbol}",
        f"├ Quantidade: {notification.size:.8f} BTC",
        f"├ Preço: ${notification.price:,.2f}",
    ]

    if notification.side == "buy":
        lines.append(f"├ Total: ${notification.funds:,.2f}")

    if notification.side == "sell" and notification.pnl != 0:
        pnl_emoji = "📈" if notification.pnl > 0 else "📉"
        lines.extend(
            [
                f"├ PnL: ${notification.pnl:,.2f}",
                f"├ Variação: {notification.pnl_pct:+.2f}%",
                f"└ {pnl_emoji} {'Lucro' if notification.pnl > 0 else 'Prejuízo'}",
            ]
        )
    else:
        lines.append(f"└ Tipo: {trade_type_str}")

    lines.extend(
        ["", f"⚙️ {mode}", f"🕐 {notification.timestamp.strftime('%d/%m/%Y %H:%M:%S')}"]
    )

    return "\n".join(lines)


def notify_trade(notification: TradeNotification, chat_id: str = None) -> bool:
    """
    Notifica sobre um trade executado

    Args:
        notification: Dados do trade
        chat_id: Chat para enviar (usa NOTIFICATION_CHAT se não especificado)

    Returns:
        True se enviou com sucesso
    """
    chat = chat_id or NOTIFICATION_CHAT
    if not chat:
        logger.debug("WhatsApp notifications desabilitadas (sem chat_id)")
        return False

    message = format_trade_message(notification)
    return send_whatsapp_message(chat, message)


def notify_buy(
    symbol: str,
    size: float,
    price: float,
    funds: float,
    trade_type: str = "auto",
    dry_run: bool = True,
    chat_id: str = None,
) -> bool:
    """
    Notifica sobre uma compra

    Args:
        symbol: Par de trading (ex: "BTC-USDT")
        size: Quantidade de BTC comprada
        price: Preço de compra
        funds: Valor em USDT
        trade_type: Tipo de trade
        dry_run: Se é simulação
        chat_id: Chat para enviar

    Returns:
        True se enviou com sucesso
    """
    notification = TradeNotification(
        side="buy",
        symbol=symbol,
        size=size,
        price=price,
        funds=funds,
        trade_type=trade_type,
        dry_run=dry_run,
    )
    return notify_trade(notification, chat_id)


def notify_sell(
    symbol: str,
    size: float,
    price: float,
    pnl: float = 0.0,
    pnl_pct: float = 0.0,
    trade_type: str = "auto",
    dry_run: bool = True,
    chat_id: str = None,
) -> bool:
    """
    Notifica sobre uma venda

    Args:
        symbol: Par de trading
        size: Quantidade de BTC vendida
        price: Preço de venda
        pnl: Lucro/prejuízo em USDT
        pnl_pct: Variação percentual
        trade_type: Tipo de trade
        dry_run: Se é simulação
        chat_id: Chat para enviar

    Returns:
        True se enviou com sucesso
    """
    notification = TradeNotification(
        side="sell",
        symbol=symbol,
        size=size,
        price=price,
        pnl=pnl,
        pnl_pct=pnl_pct,
        trade_type=trade_type,
        dry_run=dry_run,
    )
    return notify_trade(notification, chat_id)


def notify_error(error_message: str, chat_id: str = None) -> bool:
    """
    Notifica sobre um erro

    Args:
        error_message: Mensagem de erro
        chat_id: Chat para enviar

    Returns:
        True se enviou com sucesso
    """
    chat = chat_id or NOTIFICATION_CHAT
    if not chat:
        return False

    message = f"""⚠️ *ERRO NO BOT DE TRADING* ⚠️

❌ {error_message}

🕐 {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}"""

    return send_whatsapp_message(chat, message)


def notify_status(stats: Dict[str, Any], chat_id: str = None) -> bool:
    """
    Envia status do engine

    Args:
        stats: Estatísticas do engine
        chat_id: Chat para enviar

    Returns:
        True se enviou com sucesso
    """
    chat = chat_id or NOTIFICATION_CHAT
    if not chat:
        return False

    state = stats.get("state", "unknown")
    state_emoji = {"running": "🟢", "paused": "🟡", "stopped": "🔴", "error": "❌"}.get(
        state, "⚪"
    )

    message = f"""📊 *STATUS DO BOT DE TRADING*

{state_emoji} Estado: {state.upper()}

📈 *Estatísticas:*
├ Trades: {stats.get("trades_executed", 0)}
├ Win Rate: {stats.get("win_rate", 0) * 100:.1f}%
├ PnL Total: ${stats.get("total_pnl", 0):,.2f}
├ PnL Hoje: ${stats.get("daily_pnl", 0):,.2f}
└ Posição: {stats.get("current_position", 0):.8f} BTC

🕐 {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}"""

    return send_whatsapp_message(chat, message)


# ====================== TEST ======================
if __name__ == "__main__":
    # Teste
    print("🧪 Testando notificações WhatsApp...")

    # Testar envio de mensagem simples
    if NOTIFICATION_CHAT:
        # Teste de compra
        notify_buy(
            symbol="BTC-USDT",
            size=0.001,
            price=45000.0,
            funds=45.0,
            trade_type="manual",
            dry_run=True,
        )

        # Teste de venda com lucro
        notify_sell(
            symbol="BTC-USDT",
            size=0.001,
            price=46000.0,
            pnl=10.0,
            pnl_pct=2.22,
            trade_type="take_profit",
            dry_run=True,
        )

        print("✅ Mensagens de teste enviadas!")
    else:
        print("⚠️ Configure BTC_NOTIFICATION_CHAT para testar")
        print("Ex: export BTC_NOTIFICATION_CHAT='5511999999999@c.us'")
