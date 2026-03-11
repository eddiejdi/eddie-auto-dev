# Email de Boas-vindas Homelab - Guia de Implementação

## 📧 Arquivo Principal
- **Arquivo:** `docs/EMAIL_ONBOARDING_HOMELAB.html`
- **Tamanho:** ~50KB
- **Compatível com:** Gmail, Outlook, Apple Mail, Thunderbird, etc.

---

## 🖼️ Como Adicionar GIFs e Imagens

### Opção 1: Imagens Hospedadas (Recomendado para Email)

Adicione estas linhas ao HTML onde quiser os GIFs:

#### Animação - Conectando ao Homelab
```html
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/l0HlDtKPoYJSzvASU/giphy.gif" 
         alt="SSH Terminal Connection" 
         style="max-width: 100%; height: 300px;">
    <p><strong>SSH em ação: Conectando ao homelab</strong></p>
</div>
```

#### Animação - Dashboard Grafana
```html
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/3o7ZetQ5ohtA27SEGM/giphy.gif" 
         alt="Real-time Dashboard" 
         style="max-width: 100%; height: 300px;">
    <p><strong>Grafana: Monitoramento em tempo real</strong></p>
</div>
```

#### Animação - Upload Cloud
```html
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/3oKIPnAiaMCQbIiVdm/giphy.gif" 
         alt="Cloud Upload" 
         style="max-width: 100%; height: 300px;">
    <p><strong>Nextcloud: Seu cloud pessoal 1TB</strong></p>
</div>
```

#### Animação - Análise de Dados
```html
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/l46CyB1BpbSEFSOjK/giphy.gif" 
         alt="Data Analysis" 
         style="max-width: 100%; height: 300px;">
    <p><strong>PostgreSQL: Análise de dados avançada</strong></p>
</div>
```

---

## 🎬 GIFs Recomendados por Giphy

### Temas Tecnologia
- **Terminal/SSH:** `l0HlDtKPoYJSzvASU`
- **Dashboard:** `3o7ZetQ5ohtA27SEGM`
- **Cloud:** `3oKIPnAiaMCQbIiVdm`
- **Data:** `l46CyB1BpbSEFSOjK`
- **AI/Rocket:** `xuXzcHta5uUJi`
- **Security:** `l0MYt5jPR6QX5pnqM`

### Site para encontrar GIFs
- 🎬 [Giphy.com](https://giphy.com) - Busque "terminal", "dashboard", "cloud", "data"
- 🎥 [Tenor.com](https://tenor.com) - Alternativa a Giphy
- 💻 [Unsplash](https://unsplash.com) - Imagens estáticas

---

## 📝 Onde Adicionar os GIFs no HTML

### Exemplo Completo - Seção OpenWebUI
```html
<div class="section">
    <h2>🤖 Inteligência Artificial & LLM</h2>
    
    <div class="gif-placeholder">
        <img src="https://media.giphy.com/media/xuXzcHta5uUJi/giphy.gif" 
             alt="AI Assistant" 
             style="max-width: 100%; height: 250px;">
    </div>
    
    <p>Acesse o OpenWebUI para conversar com modelos LLM avançados:</p>
    <table>
        ...
    </table>
</div>
```

---

## 📧 Script Python para Enviar o Email

### Arquivo: `scripts/send_onboarding_email.py`

```python
#!/usr/bin/env python3
"""
Script para enviar email de onboarding do homelab
Requer credenciais SMTP do servidor de email corporativo
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import argparse
import sys
from typing import List

# Configuração SMTP
SMTP_HOST = "mail.rpa4all.com"
SMTP_PORT = 587
FROM_EMAIL = "admin@rpa4all.com"
FROM_NAME = "HomeLab Admin"

def send_onboarding_email(
    recipient_email: str,
    recipient_name: str = "Novo Membro",
    smtp_password: str = None,
    dry_run: bool = False
) -> bool:
    """
    Envia email de boas-vindas do homelab
    
    Args:
        recipient_email: Email do destinatário
        recipient_name: Nome completo do destinatário
        smtp_password: Senha SMTP (será solicitada se não fornecida)
        dry_run: Apenas simula, não envia
    
    Returns:
        True se sucesso, False caso contrário
    """
    
    # Ler arquivo HTML
    html_file = Path(__file__).parent.parent / "docs" / "EMAIL_ONBOARDING_HOMELAB.html"
    
    if not html_file.exists():
        print(f"❌ Erro: Arquivo não encontrado: {html_file}")
        return False
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Criar mensagem
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "🏠 Bem-vindo ao HomeLab - Guia de Onboarding"
    msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg['To'] = recipient_email
    
    # Versão em texto (fallback)
    text_content = f"""
Bem-vindo ao HomeLab!

Você foi adicionado ao sistema de computação distribuída.

Acesso rápido:
- SSH: ssh homelab@192.168.15.2
- OpenWebUI: http://192.168.15.2:3000
- Grafana: http://192.168.15.2:3002
- Nextcloud: http://192.168.15.2:8880
- Authentik SSO: https://192.168.15.2:9000

Verifique a versão HTML para instruções completas e visuais.

Suporte: admin@rpa4all.com
"""
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    # Teste
    if dry_run:
        print(f"✅ DRY RUN - Email preparado para: {recipient_email}")
        print(f"   Assunto: {msg['Subject']}")
        print(f"   Tamanho: {len(html_content)} bytes")
        return True
    
    # Enviar
    try:
        if not smtp_password:
            smtp_password = input(f"SMTP Password para {FROM_EMAIL}: ").strip()
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(FROM_EMAIL, smtp_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email enviado com sucesso para: {recipient_email}")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print(f"❌ Erro: Credenciais SMTP inválidas")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Enviar email de onboarding do homelab")
    parser.add_argument('emails', nargs='+', help="Email(s) do(s) destinatário(s)")
    parser.add_argument('--password', help="Senha SMTP (será solicitada se não fornecido)")
    parser.add_argument('--dry-run', action='store_true', help="Simula envio sem enviar")
    parser.add_argument('--batch', action='store_true', help="Modo batch: ler emails de arquivo")
    
    args = parser.parse_args()
    
    emails = []
    
    if args.batch and len(args.emails) == 1:
        # Ler de arquivo
        try:
            with open(args.emails[0], 'r') as f:
                emails = [line.strip() for line in f if line.strip() and '@' in line]
        except FileNotFoundError:
            print(f"❌ Arquivo não encontrado: {args.emails[0]}")
            return 1
    else:
        emails = args.emails
    
    success_count = 0
    
    for email in emails:
        if send_onboarding_email(
            recipient_email=email,
            smtp_password=args.password,
            dry_run=args.dry_run
        ):
            success_count += 1
    
    print(f"\n📊 Resultado: {success_count}/{len(emails)} emails enviados com sucesso")
    return 0 if success_count == len(emails) else 1

if __name__ == '__main__':
    sys.exit(main())
```

### Uso do Script

#### Enviar para um email:
```bash
python scripts/send_onboarding_email.py novo.membro@empresa.com
```

#### Enviar para múltiplos emails:
```bash
python scripts/send_onboarding_email.py email1@empresa.com email2@empresa.com email3@empresa.com
```

#### Ler de arquivo (um email por linha):
```bash
# Criar arquivo emails.txt com:
# novo.membro@empresa.com
# outro.membro@empresa.com

python scripts/send_onboarding_email.py emails.txt --batch
```

#### Modo teste (dry-run):
```bash
python scripts/send_onboarding_email.py novo.membro@empresa.com --dry-run
```

---

## 📋 Customizações Recomendadas

### 1. Adicione Imagens Corporativas
No início do `<header>`:
```html
<img src="seu-logo.png" alt="Logo Empresa" style="max-width: 200px; margin-bottom: 20px;">
```

### 2. Personalize Credenciais
Substitua nas tabelas:
- `homelab` → seu IP real
- `192.168.15.2` → seu IP
- `rpa4all.com` → seu domínio

### 3. Adicione Links Internos
Substitua placeholder links:
```html
<a href="https://suadocumentacao.com/homelab">Documentação Completa</a>
```

### 4. Configure SMTP Corporativo
Atualize variáveis em `send_onboarding_email.py`:
```python
SMTP_HOST = "seu-smtp.com"
SMTP_PORT = 587
FROM_EMAIL = "seu-email@empresa.com"
```

---

## 🎨 Templates de GIFs por Contexto

### Para Deep Dive Técnico
```html
<!-- Section IA -->
<img src="https://media.giphy.com/media/xuXzcHta5uUJi/giphy.gif">

<!-- Section Monitoramento -->
<img src="https://media.giphy.com/media/3o7ZetQ5ohtA27SEGM/giphy.gif">

<!-- Section Cloud -->
<img src="https://media.giphy.com/media/3oKIPnAiaMCQbIiVdm/giphy.gif">

<!-- Section Trading -->
<img src="https://media.giphy.com/media/13HgwGssSe2Sty/giphy.gif">
```

---

## ✅ Checklist de Implementação

- [ ] Abrir `EMAIL_ONBOARDING_HOMELAB.html` em navegador para visualizar
- [ ] Customizar com logo corporativo
- [ ] Adicionar GIFs nas seções principais
- [ ] Atualizar credenciais/IPs/domínios
- [ ] Configurar `send_onboarding_email.py` com dados SMTP reais
- [ ] Testar envio (dry-run)
- [ ] Enviar para primeira pessoa (teste real)
- [ ] Recolher feedback e ajustar
- [ ] Configurar como padrão em onboarding

---

## 📞 Suporte

Para customizações avançadas:
- Editar CSS: Modifique a seção `<style>`
- Adicionar seções: Copie `.section` div existente
- Mudar cores: Procure `#667eea` (roxo) e `#764ba2` (escuro)

Bom onboarding! 🚀
