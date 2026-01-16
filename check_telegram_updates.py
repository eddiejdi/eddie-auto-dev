#!/usr/bin/env python3
"""Verificar atualizações do Telegram (cliques nos botões)"""
import asyncio
from telegram import Bot

TELEGRAM_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"

async def check_updates():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    print("=== ATUALIZAÇÕES DO TELEGRAM ===\n")
    
    updates = await bot.get_updates(limit=20)
    
    if not updates:
        print("Nenhuma atualização pendente.")
        return
    
    for u in updates:
        print(f"Update ID: {u.update_id}")
        
        if u.callback_query:
            cb = u.callback_query
            print(f"  🔘 CALLBACK QUERY:")
            print(f"     Data: {cb.data}")
            print(f"     User: {cb.from_user.first_name} ({cb.from_user.id})")
            print(f"     Message ID: {cb.message.message_id if cb.message else 'N/A'}")
        
        if u.message and u.message.text:
            print(f"  💬 MESSAGE:")
            print(f"     Text: {u.message.text[:200]}")
            print(f"     From: {u.message.from_user.first_name if u.message.from_user else 'N/A'}")
        
        print("")

if __name__ == "__main__":
    asyncio.run(check_updates())
