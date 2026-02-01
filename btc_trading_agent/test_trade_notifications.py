#!/usr/bin/env python3
"""Teste de notificações WhatsApp para trades"""

import sys

sys.path.insert(0, "/home/homelab/myClaude/btc_trading_agent")

from whatsapp_notifications import notify_buy, notify_sell

# Teste de compra
print("Enviando notificação de COMPRA de teste...")
result1 = notify_buy(
    symbol="BTC-USDT",
    size=0.00169301,
    price=90561.15,
    funds=153.32,
    trade_type="auto",
    dry_run=False,
    chat_id="5511981193899@c.us",
)
print(f"Compra: {result1}")

# Teste de venda com lucro
print("Enviando notificação de VENDA de teste...")
result2 = notify_sell(
    symbol="BTC-USDT",
    size=0.00169301,
    price=90641.00,
    pnl=0.14,
    pnl_pct=0.09,
    trade_type="auto",
    dry_run=False,
    chat_id="5511981193899@c.us",
)
print(f"Venda: {result2}")
