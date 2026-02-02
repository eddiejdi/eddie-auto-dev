#!/usr/bin/env python3
"""
Script para Limpeza de Emails - Eddie Assistant
Lê, analisa e limpa emails irrelevantes

Uso:
    python email_cleaner_runner.py --analyze     # Apenas analisar
    python email_cleaner_runner.py --clean       # Executar limpeza (prévia)
    python email_cleaner_runner.py --clean --confirm  # Confirmar limpeza
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

from gmail_integration import get_gmail_client, get_email_cleaner, process_gmail_command


async def interactive_menu():
    """Menu interativo para gerenciar emails"""
    gmail = get_gmail_client()
    cleaner = get_email_cleaner()

    print("\n" + "=" * 60)
    print("📧 EDDIE EMAIL MANAGER - Gerenciador de Emails")
    print("=" * 60)

    # Verificar autenticação
    if not gmail.is_authenticated():
        print("\n⚠️ Não autenticado com Gmail")
        success, msg = await gmail.authenticate()
        print(msg)

        if not success:
            auth_code = input("\n📝 Cole o código de autorização: ").strip()
            if auth_code:
                success, msg = await gmail.authenticate(auth_code)
                print(msg)

        if not success:
            print("\n❌ Autenticação necessária. Tente novamente.")
            return

    print(f"\n✅ Autenticado como: {gmail.user_email}")

    while True:
        print("\n" + "-" * 40)
        print("📋 MENU:")
        print("1. 📊 Analisar caixa de entrada")
        print("2. 📬 Listar emails")
        print("3. 🔍 Ver prévia da limpeza")
        print("4. 🧹 Executar limpeza (mover para lixeira)")
        print("5. 📭 Ver não lidos")
        print("6. 🏷️ Ver labels/pastas")
        print("0. 🚪 Sair")
        print("-" * 40)

        choice = input("\nEscolha uma opção: ").strip()

        if choice == "0":
            print("\n👋 Até logo!")
            break

        elif choice == "1":
            print("\n🔄 Analisando...")
            report = await cleaner.generate_report(max_emails=100)
            print("\n" + report)

        elif choice == "2":
            try:
                count = int(input("Quantos emails? [20]: ").strip() or "20")
            except:
                count = 20

            print(f"\n🔄 Buscando {count} emails...")
            result = await process_gmail_command("listar", str(count))
            print("\n" + result)

        elif choice == "3":
            print("\n🔄 Gerando prévia...")
            result = await process_gmail_command("limpar", "")
            print("\n" + result)

        elif choice == "4":
            print(
                "\n⚠️ ATENÇÃO: Isso moverá emails de spam e promoções para a lixeira!"
            )
            confirm = input("Tem certeza? (digite 'SIM' para confirmar): ").strip()

            if confirm == "SIM":
                print("\n🔄 Executando limpeza...")
                result = await process_gmail_command("limpar", "confirmar")
                print("\n" + result)
            else:
                print("❌ Operação cancelada.")

        elif choice == "5":
            result = await process_gmail_command("nao_lidos", "")
            print("\n" + result)

        elif choice == "6":
            result = await process_gmail_command("labels", "")
            print("\n" + result)

        else:
            print("❌ Opção inválida")


async def analyze_only():
    """Apenas analisa os emails"""
    gmail = get_gmail_client()

    if not gmail.is_authenticated():
        success, msg = await gmail.authenticate()
        if not success:
            print(msg)
            return

    cleaner = get_email_cleaner()
    report = await cleaner.generate_report(max_emails=100)
    print(report)


async def run_cleanup(confirm: bool = False):
    """Executa a limpeza"""
    gmail = get_gmail_client()

    if not gmail.is_authenticated():
        success, msg = await gmail.authenticate()
        if not success:
            print(msg)
            return

    cleaner = get_email_cleaner()

    if confirm:
        result = await cleaner.clean_spam_and_promotions(dry_run=False, max_emails=100)
        print(f"""
🧹 LIMPEZA EXECUTADA!

📊 Analisados: {result["analyzed"]} emails
🚫 Spam: {result["spam_found"]}
📢 Promoções: {result["promotional_found"]}
🗑️ Movidos para lixeira: {result["deleted"]}
""")
    else:
        result = await cleaner.clean_spam_and_promotions(dry_run=True, max_emails=100)

        print(f"""
🔍 PRÉVIA DA LIMPEZA (nenhuma ação executada)

📊 Analisados: {result["analyzed"]} emails
🚫 Spam encontrado: {result["spam_found"]}
📢 Promoções encontradas: {result["promotional_found"]}
🗑️ Total a ser movido: {result["to_delete"]}

📋 Emails que serão movidos:
""")

        for email_data in result.get("emails_to_delete", [])[:15]:
            print(f"  • {email_data['subject'][:50]}")
            print(f"    De: {email_data['sender_email']}")
            print()

        if result["to_delete"] > 15:
            print(f"  ... e mais {result['to_delete'] - 15} emails\n")

        print("⚠️ Para confirmar: python email_cleaner_runner.py --clean --confirm")


async def setup_auth():
    """Configura autenticação"""
    gmail = get_gmail_client()

    print("\n🔐 CONFIGURAÇÃO DE AUTENTICAÇÃO GMAIL\n")

    success, msg = await gmail.authenticate()
    print(msg)

    if not success and "Acesse" in msg:
        print("\n📝 Cole o código de autorização abaixo:")
        auth_code = input("> ").strip()

        if auth_code:
            success, msg = await gmail.authenticate(auth_code)
            print("\n" + msg)


def main():
    parser = argparse.ArgumentParser(
        description="Eddie Email Manager - Gerenciador de Emails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python email_cleaner_runner.py                    # Menu interativo
  python email_cleaner_runner.py --auth             # Configurar autenticação
  python email_cleaner_runner.py --analyze          # Apenas analisar
  python email_cleaner_runner.py --clean            # Prévia da limpeza
  python email_cleaner_runner.py --clean --confirm  # Executar limpeza
        """,
    )

    parser.add_argument("--auth", action="store_true", help="Configurar autenticação")
    parser.add_argument("--analyze", action="store_true", help="Analisar emails")
    parser.add_argument("--clean", action="store_true", help="Executar limpeza")
    parser.add_argument("--confirm", action="store_true", help="Confirmar limpeza")

    args = parser.parse_args()

    if args.auth:
        asyncio.run(setup_auth())
    elif args.analyze:
        asyncio.run(analyze_only())
    elif args.clean:
        asyncio.run(run_cleanup(confirm=args.confirm))
    else:
        asyncio.run(interactive_menu())


if __name__ == "__main__":
    main()
