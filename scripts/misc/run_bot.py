#!/usr/bin/env python3
"""Script para rodar o bot com logging detalhado"""
import asyncio
import sys
from datetime import datetime
from telegram_bot import TelegramBot

async def run_bot_with_logging():
    print(f"[{datetime.now()}] Iniciando bot com logging...")
    sys.stdout.flush()
    
    bot = TelegramBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n[Bot] Encerrado pelo usuário")
    except Exception as e:
        print(f"[Erro] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(run_bot_with_logging())
