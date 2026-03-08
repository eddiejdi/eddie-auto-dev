#!/usr/bin/env python3
"""
Script para configurar e testar integração com Telegram
"""
import os
import sys
import asyncio

sys.path.insert(0, "/home/homelab/myClaude")

from specialized_agents.telegram_client import TelegramClient, TelegramConfig


async def setup_telegram():
    print("=" * 60)
    print("🔧 CONFIGURAÇÃO DO TELEGRAM")
    print("=" * 60)
    
    # Verificar se já está configurado
    existing_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    existing_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if existing_token and existing_chat:
        print(f"\n📋 Configuração existente encontrada:")
        print(f"   Token: {existing_token[:15]}...")
        print(f"   Chat ID: {existing_chat}")
        
        use_existing = input("\nUsar configuração existente? [S/n]: ").strip().lower()
        if use_existing != 'n':
            return existing_token, existing_chat
    
    print("\n📖 INSTRUÇÕES:")
    print("-" * 40)
    print("1. Abra o Telegram e procure por @BotFather")
    print("2. Envie /newbot e siga as instruções")
    print("3. Copie o token que ele fornecer")
    print("4. Envie uma mensagem para seu novo bot")
    print("5. Acesse: https://api.telegram.org/bot<TOKEN>/getUpdates")
    print("6. Procure por 'chat':{'id': NUMERO}")
    print("-" * 40)
    
    # Solicitar token
    token = input("\n🔑 Cole o BOT TOKEN: ").strip()
    if not token:
        print("❌ Token não pode estar vazio!")
        return None, None
    
    # Verificar token
    print("\n🔍 Verificando token...")
    config = TelegramConfig(bot_token=token, chat_id="0")
    client = TelegramClient(config)
    
    me = await client.get_me()
    if not me.get("success"):
        print(f"❌ Token inválido: {me.get('error')}")
        return None, None
    
    bot_info = me["data"]
    print(f"✅ Bot encontrado: @{bot_info.get('username')}")
    
    # Solicitar chat_id
    print("\n💡 Envie uma mensagem para seu bot no Telegram e pressione Enter...")
    input()
    
    # Buscar chat_id das atualizações
    updates = await client.get_updates()
    chat_id = None
    
    if updates.get("success") and updates.get("data"):
        for update in updates["data"]:
            if "message" in update:
                chat_id = str(update["message"]["chat"]["id"])
                chat_name = update["message"]["chat"].get("first_name", "")
                print(f"✅ Chat encontrado: {chat_name} (ID: {chat_id})")
                break
    
    if not chat_id:
        chat_id = input("❓ Chat ID não encontrado automaticamente. Digite manualmente: ").strip()
    
    if not chat_id:
        print("❌ Chat ID não pode estar vazio!")
        return None, None
    
    return token, chat_id


async def save_config(token: str, chat_id: str):
    """Salva configuração no .env"""
    env_path = "/home/homelab/myClaude/.env"
    
    # Ler .env existente
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            existing_lines = [l for l in f.readlines() 
                           if not l.startswith("TELEGRAM_")]
    
    # Adicionar novas configurações
    with open(env_path, 'w') as f:
        for line in existing_lines:
            f.write(line)
        f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
        f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")
    
    print(f"\n💾 Configuração salva em {env_path}")
    
    # Exportar para ambiente atual
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_CHAT_ID"] = chat_id


async def test_telegram():
    """Testa envio de mensagem"""
    client = TelegramClient.from_env()
    
    if not client.is_configured():
        print("❌ Telegram não configurado!")
        return False
    
    print("\n📤 Enviando mensagem de teste...")
    result = await client.send_message(
        "🤖 <b>Shared Coder Bot</b>\n\n"
        "✅ Integração configurada com sucesso!\n\n"
        "Este bot irá enviar notificações sobre:\n"
        "• Deploys e atualizações\n"
        "• Tarefas dos agentes\n"
        "• Alertas do sistema"
    )
    
    if result.get("success"):
        print("✅ Mensagem enviada com sucesso!")
        return True
    else:
        print(f"❌ Erro: {result.get('error')}")
        return False


async def main():
    # Configurar
    token, chat_id = await setup_telegram()
    
    if not token or not chat_id:
        print("\n❌ Configuração cancelada.")
        return
    
    # Salvar
    await save_config(token, chat_id)
    
    # Testar
    success = await test_telegram()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ TELEGRAM CONFIGURADO COM SUCESSO!")
        print("=" * 60)
        print("\nUso no código:")
        print("-" * 40)
        print("""
from specialized_agents.telegram_client import send_telegram, notify

# Mensagem simples
await send_telegram("Olá do Shared Coder!")

# Notificação formatada
await notify("Deploy", "App v1.0 publicado", level="success")
""")
    else:
        print("\n⚠️ Configuração salva, mas teste falhou. Verifique as credenciais.")


if __name__ == "__main__":
    asyncio.run(main())
