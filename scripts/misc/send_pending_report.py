import os
import asyncio
from telegram_bot import TelegramAPI

async def main():
    chat_id = int(os.getenv("ADMIN_CHAT_ID", "948686300"))
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN não configurado!")
        return
    api = TelegramAPI(token)
    with open("relatorio_pendencias.txt", "r", encoding="utf-8") as f:
        texto = f.read()
    await api.send_message(chat_id, texto[:4096])

if __name__ == "__main__":
    asyncio.run(main())
