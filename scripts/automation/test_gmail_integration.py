#!/usr/bin/env python3
"""
Teste da Integração Gmail
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Testa se os imports funcionam"""
    print("🔄 Testando imports...")
    
    try:
        from gmail_integration import (
            SCOPES,
            Email,
            EmailClassifier,
            EmailCleaner,
            GmailClient,
            get_email_cleaner,
            get_gmail_client,
            process_gmail_command,
        )
        print("✅ Imports OK")
        return True
    except ImportError as e:
        print(f"❌ Erro de import: {e}")
        return False

def test_classifier():
    """Testa o classificador de emails"""
    print("\n🔄 Testando classificador...")
    
    from datetime import datetime

    from gmail_integration import Email, EmailClassifier
    
    classifier = EmailClassifier()
    
    # Email de spam
    spam_email = Email(
        id="1",
        thread_id="1",
        subject="🎉 VOCÊ GANHOU! Clique aqui para receber seu prêmio GRÁTIS!",
        sender="Marketing",
        sender_email="noreply@marketing-promo.com",
        recipient="edenilson.teixeira@rpa4all.com",
        date=datetime.now(),
        snippet="Parabéns! Você foi selecionado para ganhar...",
        labels=['CATEGORY_PROMOTIONS']
    )
    
    classified = classifier.classify(spam_email)
    print(f"  Spam email score: {classified.spam_score}")
    print(f"  É spam: {classified.is_spam}")
    print(f"  Razão: {classified.classification_reason}")
    
    assert classified.spam_score > 30, "Email de spam deveria ter score alto"
    assert classified.is_spam or classified.is_promotional, "Deveria ser classificado como spam/promo"
    
    # Email importante
    important_email = Email(
        id="2",
        thread_id="2",
        subject="Re: Reunião amanhã - Edenilson",
        sender="João Silva",
        sender_email="joao@gmail.com",
        recipient="edenilson.teixeira@rpa4all.com",
        date=datetime.now(),
        snippet="Oi Edenilson, confirmando nossa reunião...",
        labels=['IMPORTANT', 'CATEGORY_PERSONAL']
    )
    
    classified = classifier.classify(important_email)
    print(f"\n  Important email score: {classified.spam_score}")
    print(f"  É importante: {classified.is_important}")
    print(f"  Razão: {classified.classification_reason}")
    
    assert classified.spam_score < 0, "Email importante deveria ter score negativo"
    assert classified.is_important or classified.is_personal, "Deveria ser classificado como importante"
    
    print("✅ Classificador OK")
    return True

def test_client_creation():
    """Testa criação do cliente"""
    print("\n🔄 Testando criação do cliente...")
    
    from gmail_integration import get_email_cleaner, get_gmail_client
    
    client = get_gmail_client()
    print(f"  Cliente criado: {type(client).__name__}")
    print(f"  Autenticado: {client.is_authenticated()}")
    
    cleaner = get_email_cleaner()
    print(f"  Cleaner criado: {type(cleaner).__name__}")
    
    print("✅ Cliente OK")
    return True

async def test_commands():
    """Testa processamento de comandos"""
    print("\n🔄 Testando comandos...")
    
    from gmail_integration import process_gmail_command
    
    # Comando ajuda
    result = await process_gmail_command('ajuda', '')
    assert "📧 **Comandos do Gmail:**" in result, "Ajuda deveria conter header"
    print("  ✅ /gmail ajuda OK")
    
    # Comando desconhecido
    result = await process_gmail_command('xyz123', '')
    assert "não reconhecido" in result.lower(), "Deveria indicar comando desconhecido"
    print("  ✅ Comando desconhecido OK")
    
    print("✅ Comandos OK")
    return True

async def test_auth_flow():
    """Testa fluxo de autenticação (sem executar de verdade)"""
    print("\n🔄 Testando fluxo de autenticação...")
    
    from gmail_integration import get_gmail_client
    
    client = get_gmail_client()
    
    if not client.is_authenticated():
        print("  ⚠️ Não autenticado - isso é esperado em ambiente de teste")
        print("  Para autenticar, execute: python email_cleaner_runner.py --auth")
    else:
        print(f"  ✅ Autenticado como: {client.user_email}")
    
    return True

def main():
    """Executa todos os testes"""
    print("="*60)
    print("🧪 TESTE DA INTEGRAÇÃO GMAIL")
    print("="*60)
    
    results = []
    
    # Testes síncronos
    results.append(("Imports", test_imports()))
    results.append(("Classificador", test_classifier()))
    results.append(("Cliente", test_client_creation()))
    
    # Testes assíncronos
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    results.append(("Comandos", loop.run_until_complete(test_commands())))
    results.append(("Auth Flow", loop.run_until_complete(test_auth_flow())))
    
    loop.close()
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("🎉 Todos os testes passaram!")
    else:
        print("⚠️ Alguns testes falharam")
        sys.exit(1)

if __name__ == "__main__":
    main()
