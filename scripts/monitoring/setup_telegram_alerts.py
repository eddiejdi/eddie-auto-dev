#!/usr/bin/env python3
"""
Configurador de Alertas Telegram para Validações
Salva credenciais Telegram de forma segura
"""

import json
import sys
from pathlib import Path


def setup_telegram():
    """Setup interativo das credenciais Telegram"""
    
    print("\n" + "="*70)
    print("🤖 Configuração de Alertas Telegram")
    print("="*70)
    
    print("\n📝 Você precisará de:")
    print("   1. Token do Bot Telegram (de @BotFather)")
    print("   2. Chat ID para receber alertas (use @userinfobot)")
    
    print("\n🔗 Links úteis:")
    print("   • Criar bot: https://t.me/BotFather")
    print("   • Obter Chat ID: https://t.me/userinfobot")
    print()
    
    # Input do token
    print("1️⃣  Digite seu Telegram Bot Token:")
    print("   (ex: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef)")
    token = input("   > ").strip()
    
    if not token or ":" not in token:
        print("❌ Token inválido!")
        return False
    
    # Input do chat ID
    print("\n2️⃣  Digite seu Chat ID:")
    print("   (ex: 123456789)")
    chat_id = input("   > ").strip()
    
    if not chat_id or not chat_id.isdigit():
        print("❌ Chat ID inválido!")
        return False
    
    # Salvar configuração
    config = {
        "token": token,
        "chat_id": int(chat_id)
    }
    
    config_file = Path.home() / ".telegram_config.json"
    
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        # Ajustar permissões
        config_file.chmod(0o600)
        
        print(f"\n✅ Configuração salva em: {config_file}")
        print("   (Permissões: 0600 - apenas leitura do proprietário)")
        
        # Enviar teste
        print("\n🧪 Testando conexão...")
        test_message(token, chat_id)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")
        return False


def test_message(token, chat_id):
    """Envia mensagem de teste"""
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "✅ Teste de Alertas Telegram - RPA4ALL Landing Page"
        }
        
        response = requests.post(url, json=data, timeout=5)
        
        if response.status_code == 200:
            print("✅ Teste enviado com sucesso!")
            print("   Verifique seu Telegram...")
        else:
            print(f"❌ Erro: {response.status_code}")
            print(f"   {response.text}")
            
    except ImportError:
        print("⚠️  requests não instalado, pulando teste")
    except Exception as e:
        print(f"❌ Erro no teste: {e}")


def show_config():
    """Mostra configuração atual"""
    config_file = Path.home() / ".telegram_config.json"
    
    if not config_file.exists():
        print("❌ Nenhuma configuração encontrada")
        return
    
    try:
        with open(config_file) as f:
            config = json.load(f)
        
        print("\n📋 Configuração Atual:")
        print(f"   Token: {config['token'][:20]}...***")
        print(f"   Chat ID: {config['chat_id']}")
        
    except Exception as e:
        print(f"❌ Erro ao ler configuração: {e}")


def remove_config():
    """Remove configuração"""
    config_file = Path.home() / ".telegram_config.json"
    
    if not config_file.exists():
        print("❌ Nenhuma configuração encontrada")
        return
    
    try:
        config_file.unlink()
        print("✅ Configuração removida")
    except Exception as e:
        print(f"❌ Erro ao remover: {e}")


def main():
    """Menu principal"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_telegram()
        elif command == "show":
            show_config()
        elif command == "remove":
            confirm = input("⚠️  Tem certeza? (s/n): ").lower()
            if confirm == "s":
                remove_config()
        else:
            print("Comando desconhecido!")
    else:
        # Menu interativo
        print("\n" + "="*70)
        print("🤖 Gerenciador de Alertas Telegram")
        print("="*70)
        print("\nOpções:")
        print("  1. Setup (configurar credentials)")
        print("  2. Show (mostrar configuração atual)")
        print("  3. Remove (remover configuração)")
        print("  4. Sair")
        
        choice = input("\nEscolha uma opção (1-4): ").strip()
        
        if choice == "1":
            setup_telegram()
        elif choice == "2":
            show_config()
        elif choice == "3":
            confirm = input("⚠️  Tem certeza? (s/n): ").lower()
            if confirm == "s":
                remove_config()
        elif choice == "4":
            print("Até logo!")
            sys.exit(0)
        else:
            print("❌ Opção inválida!")


if __name__ == "__main__":
    main()
