#!/usr/bin/env python3
"""
Guia Interativo para Configurar Credenciais Google
"""

import webbrowser
import os
import sys
from pathlib import Path

CREDENTIALS_PATH = Path("/home/homelab/myClaude/credentials.json")
CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"

def print_header():
    print("\n" + "="*70)
    print("🔐 CONFIGURAÇÃO DE CREDENCIAIS GOOGLE (Gmail + Calendar)")
    print("="*70)

def print_step(num, text):
    print(f"\n📌 PASSO {num}: {text}")
    print("-"*50)

def main():
    print_header()
    
    # Verificar se já existe
    if CREDENTIALS_PATH.exists():
        print(f"\n✅ Credenciais já existem em: {CREDENTIALS_PATH}")
        print("Execute: python setup_google_apis.py")
        return
    
    print("""
Para usar Gmail e Calendar, você precisa criar credenciais OAuth no Google Cloud.
Este guia vai te ajudar passo a passo.
""")
    
    input("Pressione ENTER para começar...")
    
    print_step(1, "Acessar Google Cloud Console")
    print(f"""
Vou abrir o Google Cloud Console no seu navegador.
URL: {CONSOLE_URL}

Se não abrir automaticamente, copie e cole no navegador.
""")
    
    try:
        webbrowser.open(CONSOLE_URL)
    except:
        print("⚠️ Não foi possível abrir o navegador automaticamente.")
    
    input("\nPressione ENTER quando estiver no Console...")
    
    print_step(2, "Criar ou Selecionar Projeto")
    print("""
1. No topo da página, clique no seletor de projeto
2. Crie um novo projeto chamado "Shared Assistant" ou selecione um existente
3. Aguarde o projeto ser criado (pode levar alguns segundos)
""")
    input("Pressione ENTER quando o projeto estiver selecionado...")
    
    print_step(3, "Ativar APIs")
    print("""
Você precisa ativar 2 APIs:

a) Gmail API:
   - Vá em: APIs e Serviços > Biblioteca
   - Pesquise "Gmail API"
   - Clique e depois em "ATIVAR"

b) Google Calendar API:
   - Pesquise "Google Calendar API"  
   - Clique e depois em "ATIVAR"
""")
    input("Pressione ENTER quando as APIs estiverem ativadas...")
    
    print_step(4, "Configurar Tela de Consentimento OAuth")
    print("""
1. Vá em: APIs e Serviços > Tela de consentimento OAuth
2. Selecione "Externo" e clique "Criar"
3. Preencha:
   - Nome do app: Shared Assistant
   - Email de suporte: seu email
   - Emails de contato: seu email
4. Clique "Salvar e Continuar"
5. Em "Escopos", clique "Adicionar ou remover escopos"
6. Adicione estes escopos:
   - .../auth/gmail.readonly
   - .../auth/gmail.modify
   - .../auth/calendar
7. Clique "Salvar e Continuar"
8. Em "Usuários de teste", adicione seu email
9. Clique "Salvar e Continuar"
""")
    input("Pressione ENTER quando a tela de consentimento estiver configurada...")
    
    print_step(5, "Criar Credenciais OAuth")
    print("""
1. Vá em: APIs e Serviços > Credenciais
2. Clique "+ CRIAR CREDENCIAIS"
3. Selecione "ID do cliente OAuth"
4. Tipo de aplicativo: "Aplicativo para computador"
5. Nome: "Shared CLI"
6. Clique "Criar"
7. Na janela que aparece, clique "FAZER O DOWNLOAD DO JSON"
""")
    input("Pressione ENTER quando tiver baixado o arquivo JSON...")
    
    print_step(6, "Mover arquivo de credenciais")
    print(f"""
Agora você precisa mover/copiar o arquivo baixado para:
{CREDENTIALS_PATH}

O arquivo geralmente é baixado como:
- client_secret_XXXXX.json
- credentials.json

Se estiver no Windows, o arquivo está provavelmente em:
C:\\Users\\<seu_usuario>\\Downloads\\

Você pode:
a) Mover manualmente o arquivo
b) Ou colar o caminho completo do arquivo aqui

""")
    
    downloaded_path = input("Cole o caminho do arquivo JSON baixado (ou ENTER se já moveu): ").strip()
    
    if downloaded_path:
        # Tentar converter caminho Windows para WSL se necessário
        if downloaded_path.startswith("C:") or downloaded_path.startswith("c:"):
            wsl_path = downloaded_path.replace("C:", "/mnt/c").replace("c:", "/mnt/c").replace("\\", "/")
            print(f"Convertendo para caminho WSL: {wsl_path}")
            downloaded_path = wsl_path
        
        try:
            import shutil
            source = Path(downloaded_path.strip('"').strip("'"))
            if source.exists():
                shutil.copy(source, CREDENTIALS_PATH)
                print(f"\n✅ Arquivo copiado para: {CREDENTIALS_PATH}")
            else:
                print(f"\n❌ Arquivo não encontrado: {source}")
                print("Copie manualmente o arquivo para:", CREDENTIALS_PATH)
        except Exception as e:
            print(f"\n⚠️ Erro ao copiar: {e}")
            print("Copie manualmente o arquivo para:", CREDENTIALS_PATH)
    
    # Verificar se existe agora
    if CREDENTIALS_PATH.exists():
        print_step(7, "Autenticar")
        print("""
✅ Credenciais encontradas!

Agora execute o seguinte comando para autenticar:

    cd /home/homelab/myClaude
    source venv/bin/activate
    python setup_google_apis.py

Isso vai abrir uma janela no navegador para você autorizar o acesso.
""")
    else:
        print(f"""

⚠️ Credenciais ainda não encontradas em: {CREDENTIALS_PATH}

Depois de copiar o arquivo, execute:

    cd /home/homelab/myClaude
    source venv/bin/activate
    python setup_google_apis.py
""")
    
    print("\n" + "="*70)
    print("📧 Após autenticar, use: /gmail analisar")
    print("📅 E também: /calendar listar")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
