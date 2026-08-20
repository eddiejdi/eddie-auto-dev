#!/usr/bin/env python3
"""
Setup Telegram alerts usando credenciais do Bitwarden
Cria ~/.telegram_config.json automaticamente a partir do cofre
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_bw_command(args: list[str]) -> tuple[bool, str]:
    """Executa comando bw e retorna (sucesso, output)"""
    try:
        result = subprocess.run(
            ["bw"] + args,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def search_telegram_item() -> dict | None:
    """Busca item do Telegram no Bitwarden"""
    print("🔍 Buscando credenciais do Telegram no Bitwarden...")
    
    # Tentar buscar por nome específico
    success, output = run_bw_command(["list", "items", "--search", "RPA4ALL Monitoring"])
    
    if not success or not output:
        # Tentar busca mais ampla
        success, output = run_bw_command(["list", "items"])
        if not success:
            return None
    
    try:
        items = json.loads(output)
        
        # Filtrar itens relacionados ao Telegram
        for item in items:
            name_lower = item.get("name", "").lower()
            if "telegram" in name_lower and ("rpa4all" in name_lower or "monitoring" in name_lower):
                return item
        
        # Se não encontrou, retornar primeiro item do Telegram
        for item in items:
            if "telegram" in item.get("name", "").lower():
                return item
                
    except json.JSONDecodeError:
        return None
    
    return None


def extract_credentials(item: dict) -> tuple[str | None, str | None]:
    """Extrai bot_token e chat_id do item do Bitwarden"""
    token = None
    chat_id = None
    
    # Tentar extrair de fields customizados
    fields = item.get("fields", [])
    for field in fields:
        field_name = field.get("name", "").lower()
        field_value = field.get("value", "")
        
        if "token" in field_name and field_value:
            token = field_value
        elif "chat" in field_name and field_value:
            chat_id = field_value
    
    # Fallback: tentar extrair de login
    if not token:
        login = item.get("login", {})
        password = login.get("password", "")
        if password and ":" in password:  # Formato de bot token
            token = password
    
    # Fallback: tentar extrair de notes
    if not chat_id or not token:
        notes = item.get("notes", "")
        for line in notes.split("\n"):
            if "chat_id" in line.lower() and ":" in line:
                chat_id = line.split(":", 1)[1].strip()
            elif "token" in line.lower() and ":" in line:
                token = line.split(":", 1)[1].strip()
    
    return token, chat_id


def save_telegram_config(token: str, chat_id: str) -> bool:
    """Salva configuração em ~/.telegram_config.json"""
    config_path = Path.home() / ".telegram_config.json"
    
    config = {
        "token": token,
        "chat_id": chat_id
    }
    
    try:
        # Salvar arquivo
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        
        # Definir permissões seguras (0600)
        os.chmod(config_path, 0o600)
        
        print(f"✅ Configuração salva em: {config_path}")
        print("   Permissões: 0600 (somente proprietário)")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")
        return False


def test_telegram_connection(token: str, chat_id: str) -> bool:
    """Testa conexão com Telegram enviando mensagem de teste"""
    import urllib.parse
    import urllib.request
    
    print("\n🧪 Testando conexão com Telegram...")
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": "✅ Configuração concluída!\n\nSistema de alertas RPA4ALL ativo."
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            if result.get("ok"):
                print("✅ Mensagem de teste enviada com sucesso!")
                return True
            else:
                print(f"⚠️ Erro na API: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        return False


def create_item_in_bitwarden(token: str, chat_id: str) -> bool:
    """Cria novo item no Bitwarden com as credenciais fornecidas"""
    print("\n📝 Criando item no Bitwarden...")
    
    item = {
        "type": 1,  # Login
        "name": "Telegram Bot - RPA4ALL Monitoring",
        "notes": "Bot para alertas de monitoramento\nCriado: 2026-02-02\nUso: validation_scheduler.py",
        "login": {
            "username": "rpa4all_monitoring_bot",
            "password": token
        },
        "fields": [
            {"name": "bot_token", "value": token, "type": 0},
            {"name": "chat_id", "value": chat_id, "type": 0}
        ]
    }
    
    # Salvar JSON temporário
    temp_file = "/tmp/telegram_bot_new.json"
    with open(temp_file, "w") as f:
        json.dump(item, f, indent=2)
    
    # Criar item no Bitwarden
    success, output = run_bw_command(["create", "item", temp_file])
    
    os.remove(temp_file)
    
    if success:
        print("✅ Item criado no Bitwarden")
        return True
    else:
        print(f"⚠️ Não foi possível criar item: {output}")
        return False


def manual_setup() -> tuple[str | None, str | None]:
    """Setup manual caso não encontre no Bitwarden"""
    print("\n" + "="*60)
    print("📝 SETUP MANUAL")
    print("="*60)
    print()
    print("Para obter as credenciais:")
    print("1. Bot Token: converse com @BotFather no Telegram")
    print("   - Envie: /newbot")
    print("   - Siga as instruções")
    print("   - Copie o token (formato: 1234567890:ABCdef...)")
    print()
    print("2. Chat ID: converse com @userinfobot no Telegram")
    print("   - Envie qualquer mensagem")
    print("   - Copie o ID (formato: 123456789)")
    print()
    
    token = input("Cole o Bot Token: ").strip()
    chat_id = input("Cole o Chat ID: ").strip()
    
    if not token or not chat_id:
        print("❌ Credenciais inválidas")
        return None, None
    
    # Oferecer salvar no Bitwarden
    save_to_bw = input("\n💾 Salvar no Bitwarden? (s/N): ").strip().lower()
    if save_to_bw == "s":
        create_item_in_bitwarden(token, chat_id)
    
    return token, chat_id


def main():
    print("🤖 Setup Telegram - RPA4ALL Monitoring")
    print("="*60)
    
    # Verificar se bw está disponível
    success, _ = run_bw_command(["--version"])
    if not success:
        print("❌ Bitwarden CLI não encontrado")
        print("   Instale: https://bitwarden.com/help/cli/")
        return 1
    
    # Verificar se está logado
    success, status = run_bw_command(["status"])
    if success:
        try:
            status_data = json.loads(status)
            if status_data.get("status") != "unlocked":
                print("⚠️ Bitwarden bloqueado. Execute: bw unlock")
                print()
        except:
            pass
    
    # Buscar item no Bitwarden
    item = search_telegram_item()
    
    token = None
    chat_id = None
    
    if item:
        print(f"✅ Encontrado: {item.get('name')}")
        token, chat_id = extract_credentials(item)
        
        if not token or not chat_id:
            print("⚠️ Item encontrado mas credenciais incompletas")
            print(f"   Token: {'✅' if token else '❌'}")
            print(f"   Chat ID: {'✅' if chat_id else '❌'}")
            
            use_manual = input("\nDeseja configurar manualmente? (S/n): ").strip().lower()
            if use_manual != "n":
                token, chat_id = manual_setup()
    else:
        print("⚠️ Nenhum item do Telegram encontrado no Bitwarden")
        use_manual = input("\nDeseja configurar manualmente? (S/n): ").strip().lower()
        if use_manual != "n":
            token, chat_id = manual_setup()
    
    # Validar credenciais
    if not token or not chat_id:
        print("\n❌ Credenciais não configuradas")
        return 1
    
    # Salvar configuração local
    if not save_telegram_config(token, chat_id):
        return 1
    
    # Testar conexão
    test_telegram_connection(token, chat_id)
    
    print("\n" + "="*60)
    print("✅ SETUP CONCLUÍDO")
    print("="*60)
    print()
    print("📁 Arquivo de configuração: ~/.telegram_config.json")
    print("🔐 Credenciais armazenadas com segurança")
    print()
    print("Próximos passos:")
    print("1. Instalar systemd timer: sudo bash setup_validation_timer.sh")
    print("2. Iniciar dashboard: streamlit run dashboard_validations.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
