#!/usr/bin/env python3
"""
Setup do Google Calendar para Eddie Assistant

Este script configura a autenticação OAuth2 com Google Calendar.

Passos:
1. Vá para https://console.cloud.google.com/
2. Crie um novo projeto ou selecione existente
3. Ative a Google Calendar API
4. Crie credenciais OAuth2 (tipo: Desktop application)
5. Baixe o arquivo JSON e salve como credentials.json
6. Execute este script

Autor: Eddie Assistant
Data: 2026
"""

import os
import json
import sys
from pathlib import Path

# Diretório de dados
DATA_DIR = Path(__file__).parent / "calendar_data"
DATA_DIR.mkdir(exist_ok=True)

CREDENTIALS_FILE = DATA_DIR / "credentials.json"


def create_sample_credentials():
    """Cria arquivo de exemplo de credenciais"""
    sample = {
        "installed": {
            "client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
            "project_id": "seu-projeto-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "SEU_CLIENT_SECRET",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    sample_file = DATA_DIR / "credentials_example.json"
    with open(sample_file, 'w') as f:
        json.dump(sample, f, indent=2)
    
    return sample_file


def check_credentials():
    """Verifica se as credenciais estão configuradas"""
    if not CREDENTIALS_FILE.exists():
        print("❌ Arquivo de credenciais não encontrado!")
        print(f"\n📁 Caminho esperado: {CREDENTIALS_FILE}")
        print("\n📋 Instruções para configurar:")
        print("="*60)
        print("""
1. Acesse: https://console.cloud.google.com/

2. Crie um novo projeto ou selecione existente

3. No menu lateral, vá em "APIs e Serviços" > "Biblioteca"

4. Busque e ative "Google Calendar API"

5. Vá em "APIs e Serviços" > "Credenciais"

6. Clique em "Criar Credenciais" > "ID do cliente OAuth"

7. Selecione "Aplicativo para computador"

8. Nomeie como "Eddie Assistant"

9. Baixe o JSON clicando no ícone de download

10. Renomeie para 'credentials.json' e mova para:
    {path}

11. Execute este script novamente
""".format(path=DATA_DIR))
        
        sample_file = create_sample_credentials()
        print(f"\n💡 Arquivo de exemplo criado em: {sample_file}")
        return False
    
    # Validar estrutura do arquivo
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
        
        if 'installed' not in creds and 'web' not in creds:
            print("❌ Formato inválido do arquivo de credenciais!")
            return False
        
        print("✅ Arquivo de credenciais encontrado e válido!")
        return True
        
    except json.JSONDecodeError:
        print("❌ Erro ao ler arquivo de credenciais (JSON inválido)")
        return False


def install_dependencies():
    """Instala dependências necessárias"""
    print("\n📦 Verificando dependências...")
    
    required = [
        'google-auth-oauthlib',
        'google-api-python-client',
        'python-dateutil'
    ]
    
    missing = []
    
    for package in required:
        try:
            __import__(package.replace('-', '_').split('_')[0])
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"\n⚠️ Pacotes faltando: {', '.join(missing)}")
        
        response = input("\nDeseja instalar agora? (s/n): ").strip().lower()
        if response == 's':
            import subprocess
            for package in missing:
                print(f"📥 Instalando {package}...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', package], check=True)
            print("✅ Dependências instaladas!")
        else:
            print(f"\n💡 Execute manualmente: pip install {' '.join(missing)}")
            return False
    else:
        print("✅ Todas as dependências estão instaladas!")
    
    return True


def authenticate():
    """Realiza autenticação OAuth2"""
    print("\n🔐 Iniciando autenticação...")
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import pickle
        
        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        
        TOKEN_FILE = DATA_DIR / "token.pickle"
        
        # Verificar se já tem token válido
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, 'rb') as f:
                creds = pickle.load(f)
            
            if creds and creds.valid:
                print("✅ Já autenticado!")
                
                # Testar conexão
                service = build('calendar', 'v3', credentials=creds)
                calendar = service.calendars().get(calendarId='primary').execute()
                print(f"📅 Calendário: {calendar['summary']}")
                return True
        
        # Iniciar fluxo de autenticação
        print("\n🌐 Abrindo navegador para autenticação...")
        print("   (Se não abrir automaticamente, copie a URL exibida)")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        
        creds = flow.run_local_server(port=0)
        
        # Salvar token
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
        
        print("✅ Autenticação concluída!")
        
        # Testar conexão
        service = build('calendar', 'v3', credentials=creds)
        calendar = service.calendars().get(calendarId='primary').execute()
        print(f"📅 Conectado ao calendário: {calendar['summary']}")
        
        # Listar próximos eventos como teste
        from datetime import datetime
        
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if events:
            print(f"\n📋 Próximos {len(events)} eventos:")
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"   • {start[:16]} - {event['summary']}")
        else:
            print("\n📋 Nenhum evento próximo encontrado.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro na autenticação: {e}")
        return False


def setup_environment():
    """Configura variáveis de ambiente"""
    env_file = Path(__file__).parent / ".env"
    
    # Ler .env existente
    env_vars = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
    
    # Adicionar variáveis do calendário se não existirem
    new_vars = {
        'GOOGLE_CALENDAR_ENABLED': 'true',
        'CALENDAR_REMINDER_MINUTES': '30,10',
        'CALENDAR_DAILY_DIGEST_HOUR': '7'
    }
    
    updated = False
    for key, default in new_vars.items():
        if key not in env_vars:
            env_vars[key] = default
            updated = True
    
    if updated:
        # Salvar .env atualizado
        with open(env_file, 'a') as f:
            f.write("\n# Google Calendar Integration\n")
            for key in new_vars:
                if key not in [k for k, v in env_vars.items()]:
                    f.write(f"{key}={new_vars[key]}\n")
        
        print("✅ Variáveis de ambiente configuradas!")


def create_systemd_service():
    """Cria serviço systemd para lembretes"""
    service_content = """[Unit]
Description=Eddie Calendar Reminder Service
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={python} {script}
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
""".format(
        user=os.getenv('USER', 'eddie'),
        workdir=Path(__file__).parent,
        python=sys.executable,
        script=Path(__file__).parent / "calendar_reminder_service.py"
    )
    
    service_file = Path(__file__).parent / "eddie-calendar.service"
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"\n📄 Arquivo de serviço criado: {service_file}")
    print("\n📋 Para instalar o serviço de lembretes:")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl enable eddie-calendar")
    print("   sudo systemctl start eddie-calendar")


def main():
    """Função principal de setup"""
    print("="*60)
    print("🗓️  Setup Google Calendar - Eddie Assistant")
    print("="*60)
    
    # 1. Verificar dependências
    if not install_dependencies():
        return
    
    # 2. Verificar credenciais
    if not check_credentials():
        return
    
    # 3. Autenticar
    if not authenticate():
        return
    
    # 4. Configurar ambiente
    setup_environment()
    
    # 5. Criar serviço systemd
    create_systemd_service()
    
    print("\n" + "="*60)
    print("✅ Setup concluído com sucesso!")
    print("="*60)
    print("""
📋 Próximos passos:

1. Use o bot de Telegram ou WhatsApp com comandos:
   • /calendar listar - Ver eventos
   • /calendar criar <evento> - Criar evento
   • /calendar ajuda - Ver todos comandos

2. Ou simplesmente peça:
   "Agende uma reunião para amanhã às 14h"
   "O que tenho na agenda de hoje?"

3. Para lembretes automáticos, inicie o serviço:
   sudo systemctl start eddie-calendar
""")


if __name__ == "__main__":
    main()
