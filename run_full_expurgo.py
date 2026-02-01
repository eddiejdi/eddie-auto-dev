#!/usr/bin/env python3
"""
Script para executar expurgo COMPLETO do Gmail - SEM LIMITE DE TEMPO
Processa TODOS os emails em todas as categorias
"""

import asyncio
import sys
import os

# Configurar path correto do Gmail
os.environ["GMAIL_DATA_DIR"] = "/home/eddie/myClaude/gmail_data"

sys.path.insert(0, "/home/eddie/myClaude")
from gmail_expurgo_inteligente import ExpurgoInteligente


async def run_full_expurgo():
    expurgo = ExpurgoInteligente()

    # Modificar categorias para processar TODOS os emails (sem limite de tempo)
    # Usar 1 dia como limite (ou seja, emails mais antigos que 1 dia)
    expurgo.categories = [
        ("promotions", 1),  # Promoções: mais de 1 dia
        ("social", 1),  # Social: mais de 1 dia
        ("updates", 1),  # Updates: mais de 1 dia
        ("forums", 1),  # Fóruns: mais de 1 dia
        ("spam", 1),  # Spam: mais de 1 dia
    ]

    print("=" * 60)
    print("🔥 EXPURGO COMPLETO - SEM LIMITE DE TEMPO")
    print("=" * 60)
    print("   Todas as categorias: emails > 1 dia serão processados")
    print("   Treinamento IA: Ativo")
    print("   Notificações: Telegram")
    print("=" * 60)
    print()

    result = await expurgo.run_expurgo(
        dry_run=False,
        train_emails=True,
        send_notifications=True,
        notification_channels=["telegram"],
    )

    return result


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     📧 Gmail Expurgo TOTAL - Sem Limite de Tempo 📧          ║
╚══════════════════════════════════════════════════════════════╝
""")

    result = asyncio.run(run_full_expurgo())

    if result.get("error"):
        print(f"\n❌ Erro: {result['error']}")
        sys.exit(1)

    print("\n✅ Expurgo COMPLETO finalizado!")
    print(
        f"   Emails movidos para lixeira: {result.get('stats', {}).get('deleted', 0)}"
    )
    print(f"   Emails treinados na IA: {result.get('stats', {}).get('trained', 0)}")
