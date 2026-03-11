#!/usr/bin/env python3
"""
Script para enviar email de onboarding do homelab
Requer credenciais SMTP do servidor de email corporativo

Uso:
    python send_onboarding_email.py novo.membro@empresa.com
    python send_onboarding_email.py emails.txt --batch
    python send_onboarding_email.py novo.membro@empresa.com --dry-run
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import argparse
import sys
import getpass
from typing import List, Optional

# ════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO SMTP
# ════════════════════════════════════════════════════════════════

SMTP_HOST = "mail.rpa4all.com"
SMTP_PORT = 587
FROM_EMAIL = "admin@rpa4all.com"
FROM_NAME = "HomeLab Admin"


def send_onboarding_email(
    recipient_email: str,
    recipient_name: str = "Novo Membro",
    smtp_password: Optional[str] = None,
    dry_run: bool = False
) -> bool:
    """
    Envia email de boas-vindas do homelab.
    
    Args:
        recipient_email: Email do destinatário.
        recipient_name: Nome completo do destinatário (opcional).
        smtp_password: Senha SMTP (será solicitada se não fornecida).
        dry_run: Apenas simula, não envia.
    
    Returns:
        True se sucesso, False caso contrário.
    """
    
    # Ler arquivo HTML
    html_file = Path(__file__).parent.parent / "docs" / "EMAIL_ONBOARDING_HOMELAB.html"
    
    if not html_file.exists():
        print(f"❌ Erro: Arquivo não encontrado: {html_file}")
        return False
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"❌ Erro ao ler arquivo: {e}")
        return False
    
    # Criar mensagem
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "🏠 Bem-vindo ao HomeLab - Guia de Onboarding"
    msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg['To'] = recipient_email
    
    # Versão em texto (fallback para clientes que não suportam HTML)
    text_content = f"""
════════════════════════════════════════════════════════════════
🏠 BEM-VINDO AO HOMELAB
════════════════════════════════════════════════════════════════

Olá {recipient_name}!

Você foi adicionado ao HomeLab - um ambiente de computação distribuída
de primeira classe com GPUs, IA, cloud pessoal e muito mais.

════════════════════════════════════════════════════════════════
⚡ ACESSO RÁPIDO
════════════════════════════════════════════════════════════════

SSH (Terminal):
  $ ssh homelab@192.168.15.2

Serviços Web:
  🤖 OpenWebUI (Chat IA):        http://192.168.15.2:3000
  📊 Grafana (Monitoramento):    http://192.168.15.2:3002
  ☁️  Nextcloud (Cloud 1TB):      http://192.168.15.2:8880
  📧 Roundcube (Webmail):        http://192.168.15.2:9080
  🔐 Authentik SSO:              https://192.168.15.2:9000

════════════════════════════════════════════════════════════════
📚 O QUE VOCÊ TEM ACESSO
════════════════════════════════════════════════════════════════

✅ Servidores LLM (Ollama) com 2 GPUs NVIDIA 24/7
✅ Dashboard Grafana com monitoramento em tempo real
✅ Cloud pessoal com 1TB de espaço (Nextcloud)
✅ Email corporativo @rpa4all.com
✅ Autenticação SSO para todos os serviços
✅ VPN WireGuard para acesso seguro remoto
✅ Trading automático com IA (24/7)
✅ Banco de dados PostgreSQL avançado

════════════════════════════════════════════════════════════════
🚀 PRÓXIMOS PASSOS
════════════════════════════════════════════════════════════════

1. Conecte via SSH:
   ssh homelab@192.168.15.2

2. Acesse o dashboard:
   http://192.168.15.2:3002 (Grafana)

3. Configure login único:
   https://192.168.15.2:9000 (Authentik SSO)

4. Explore a IA:
   http://192.168.15.2:3000 (OpenWebUI)

5. Envie arquivo para cloud:
   http://192.168.15.2:8880 (Nextcloud)

════════════════════════════════════════════════════════════════
📞 SUPORTE
════════════════════════════════════════════════════════════════

Precisa de ajuda?
  📧 Email: admin@rpa4all.com
  📚 Documentação: Verifique a versão HTML deste email

═════════════════════════════════════════════════════════════════

Para instruções completas e visuais, abra a versão HTML deste email.

Bem-vindo! 🎉
"""
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    # Modo teste
    if dry_run:
        print(f"✅ DRY RUN - Email preparado!")
        print(f"   Destinatário: {recipient_email}")
        print(f"   Remetente: {FROM_EMAIL}")
        print(f"   Assunto: {msg['Subject']}")
        print(f"   Tamanho: {len(html_content):,} bytes (HTML)")
        return True
    
    # Enviar email
    try:
        if not smtp_password:
            print(f"\n🔐 Autenticação SMTP")
            print(f"   Host: {SMTP_HOST}:{SMTP_PORT}")
            print(f"   Usuário: {FROM_EMAIL}")
            smtp_password = getpass.getpass("   Senha: ")
        
        print(f"📤 Conectando a {SMTP_HOST}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.set_debuglevel(0)
        server.starttls()
        
        print(f"🔐 Autenticando...")
        server.login(FROM_EMAIL, smtp_password)
        
        print(f"📧 Enviando para {recipient_email}...")
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email enviado com sucesso para: {recipient_email}\n")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print(f"❌ Erro: Credenciais SMTP inválidas\n")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ Erro SMTP: {e}\n")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="🏠 Enviar email de onboarding do homelab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Um email
  python send_onboarding_email.py novo@empresa.com
  
  # Múltiplos emails
  python send_onboarding_email.py email1@empresa.com email2@empresa.com
  
  # De arquivo (um por linha)
  python send_onboarding_email.py emails.txt --batch
  
  # Modo teste (dry-run)
  python send_onboarding_email.py novo@empresa.com --dry-run
  
  # Com senha
  python send_onboarding_email.py novo@empresa.com --password 'sua_senha'
        """
    )
    
    parser.add_argument(
        'emails',
        nargs='+',
        help="Email(s) do(s) destinatário(s) ou arquivo .txt"
    )
    parser.add_argument(
        '--password',
        help="Senha SMTP (será solicitada interativamente se não fornecido)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Simula envio sem enviar (teste)"
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help="Ler emails de arquivo (um por linha)"
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help="Modo verbose"
    )
    
    args = parser.parse_args()
    
    emails = []
    
    if args.batch and len(args.emails) == 1:
        # Ler de arquivo
        try:
            email_file = Path(args.emails[0])
            if not email_file.exists():
                print(f"❌ Arquivo não encontrado: {args.emails[0]}")
                return 1
            
            with open(email_file, 'r', encoding='utf-8') as f:
                emails = [
                    line.strip()
                    for line in f
                    if line.strip() and '@' in line
                ]
            
            print(f"📖 Arquivo lido: {len(emails)} email(s) encontrado(s)\n")
        except Exception as e:
            print(f"❌ Erro ao ler arquivo: {e}")
            return 1
    else:
        # Usar emails da linha de comando
        emails = args.emails
    
    if not emails:
        print("❌ Nenhum email fornecido")
        return 1
    
    print("=" * 60)
    print("🏠 ONBOARDING HOMELAB - EMAIL SENDER")
    print("=" * 60)
    print(f"📧 Total de destinatários: {len(emails)}")
    if args.dry_run:
        print("⚠️  Modo DRY-RUN (não será enviado)\n")
    else:
        print()
    
    success_count = 0
    failed_emails = []
    
    for i, email in enumerate(emails, 1):
        print(f"[{i}/{len(emails)}] Processando: {email}")
        
        if send_onboarding_email(
            recipient_email=email,
            smtp_password=args.password,
            dry_run=args.dry_run
        ):
            success_count += 1
        else:
            failed_emails.append(email)
    
    # Resumo
    print("=" * 60)
    print("📊 RESUMO")
    print("=" * 60)
    print(f"✅ Sucesso: {success_count}/{len(emails)}")
    if failed_emails:
        print(f"❌ Falha: {len(failed_emails)}")
        for email in failed_emails:
            print(f"   - {email}")
    
    if args.dry_run:
        print("\n⚠️  Modo DRY-RUN: nenhum email foi realmente enviado")
    
    print()
    
    return 0 if success_count == len(emails) else 1


if __name__ == '__main__':
    sys.exit(main())
