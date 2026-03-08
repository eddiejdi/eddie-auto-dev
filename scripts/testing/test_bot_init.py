#!/usr/bin/env python3
"""Script para testar o bot"""
import asyncio
from telegram_bot import TelegramBot

async def test():
    print("Iniciando teste...")
    bot = TelegramBot()
    print("Bot criado")
    await bot.clear_old_updates()
    print("Clear updates ok")
    await bot.api.close()
    print("Teste concluído!")

if __name__ == "__main__":
    asyncio.run(test())
