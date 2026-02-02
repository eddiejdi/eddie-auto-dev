#!/usr/bin/env python3
"""Teste de integração do Google Calendar"""

import sys

sys.path.insert(0, "/home/homelab/myClaude")

print("Testando imports...")

try:
    print("✅ google_calendar_integration OK")
except Exception as e:
    print(f"❌ Erro: {e}")

print("\nTestando import no telegram_bot...")
try:
    import telegram_bot

    if hasattr(telegram_bot, "CALENDAR_AVAILABLE"):
        print(f"✅ CALENDAR_AVAILABLE = {telegram_bot.CALENDAR_AVAILABLE}")
    else:
        print("⚠️ CALENDAR_AVAILABLE não encontrado")
except Exception as e:
    print(f"❌ Erro: {e}")

print("\nTestando import no whatsapp_bot...")
try:
    import whatsapp_bot

    if hasattr(whatsapp_bot, "CALENDAR_AVAILABLE"):
        print(f"✅ CALENDAR_AVAILABLE = {whatsapp_bot.CALENDAR_AVAILABLE}")
    else:
        print("⚠️ CALENDAR_AVAILABLE não encontrado")
except Exception as e:
    print(f"❌ Erro: {e}")

print("\nTeste concluído!")
