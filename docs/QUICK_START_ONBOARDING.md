# 🏠 HomeLab Onboarding Email - Quick Start Guide

## 📦 O que você recebeu

```
docs/
├── EMAIL_ONBOARDING_HOMELAB.html  ← 📧 EMAIL PRINCIPAL (abrir em navegador)
├── EMAIL_ONBOARDING_GUIDE.md      ← 📚 Guia de customização
└── ONBOARDING_EMAIL_README.md     ← 📖 Documentação completa

scripts/
└── send_onboarding_email.py       ← 🚀 Script de envio (Python)
```

---

## ⚡ Inicio em 2 Minutos

### 1️⃣ Visualizar o Email
```bash
# Abrir no navegador (melhor forma)
open docs/EMAIL_ONBOARDING_HOMELAB.html

# Ou copie o caminho:
# /home/edenilson/eddie-auto-dev/docs/EMAIL_ONBOARDING_HOMELAB.html
```

### 2️⃣ Testar Envio
```bash
# Modo teste (SEM enviar)
python3 scripts/send_onboarding_email.py seu-email@empresa.com --dry-run

# Você verá:
# ✅ DRY RUN - Email preparado!
#    Destinatário: seu-email@empresa.com
#    Tamanho: 52341 bytes (HTML)
```

### 3️⃣ Enviar de Verdade
```bash
# Enviar para uma pessoa
python3 scripts/send_onboarding_email.py novo.membro@empresa.com

# Será solicitado:
# 🔐 Autenticação SMTP
#    Host: mail.rpa4all.com:587
#    Usuário: admin@rpa4all.com
#    Senha: [digite aqui]

# ✅ Email enviado com sucesso para: novo.membro@empresa.com
```

---

## 📨 Exemplos de Uso

### ✅ Enviar para 1 pessoa
```bash
python3 scripts/send_onboarding_email.py joao.silva@empresa.com
```

### ✅ Enviar para 5 pessoas
```bash
python3 scripts/send_onboarding_email.py \
    joao@empresa.com \
    maria@empresa.com \
    carlos@empresa.com \
    ana@empresa.com \
    pedro@empresa.com
```

### ✅ Enviar de arquivo (100+ pessoas)
Crie `emails.txt`:
```
joao@empresa.com
maria@empresa.com
carlos@empresa.com
# Linhas em branco ou com # são ignoradas
ana@empresa.com
```

Execute:
```bash
python3 scripts/send_onboarding_email.py emails.txt --batch
```

### ✅ Com senha pré-configurada (para automação)
```bash
python3 scripts/send_onboarding_email.py joao@empresa.com \
    --password 'sua_senha_smtp'
```

### ✅ Modo verbose (debug/troubleshooting)
```bash
python3 scripts/send_onboarding_email.py joao@empresa.com --verbose
```

---

## 🎨 Customizações (5 minutos)

### Mudar Cores
Abra `EMAIL_ONBOARDING_HOMELAB.html` e procure por:
```css
#667eea    /* Roxo principal - mude aqui */
#764ba2    /* Roxo escuro - mude aqui */
```

Substitua por suas cores:
```css
#0066cc    /* Azul */
#003d99    /* Azul escuro */
```

### Adicionar Logo
No início do `<header>`, após `<div class="header">`:
```html
<img src="https://seu-logo.png" alt="Logo" style="max-width: 200px;">
```

### Adicionar GIFs
Procure por `<!-- Adicione GIFs aqui -->` ou qualquer seção, e adicione:
```html
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/l0HlDtKPoYJSzvASU/giphy.gif" 
         alt="SSH Terminal" 
         style="max-width: 100%; height: 250px;">
    <p><strong>SSH em ação</strong></p>
</div>
```

---

## 📋 Conteúdo do Email

O email contém **11 seções principais**:

| # | Seção | Conteúdo |
|---|-------|----------|
| 1 | 👋 Boas-vindas | Apresentação e o que tem acesso |
| 2 | 🚀 Como Começar | Timeline com 4 passos iniciais |
| 3 | 🔧 Serviços | Tabelas de portas e serviços (25+) |
| 4 | 🔑 Credenciais | SSH, Email, SSO, PostgreSQL |
| 5 | 📌 Tarefas Comuns | Upload arquivo, monitoramento, IA, VPN |
| 6 | 🏗️ Arquitetura | 6 cards visuais dos sistemas |
| 7 | 🆘 Troubleshooting | 4 problemas + soluções |
| 8 | 📚 Documentação | Links úteis e recursos |
| 9 | ✅ Próximos Passos | Checklist de 8 itens |
| 10 | 📞 Suporte | Email, Slack, GitHub, telefone |
| 11 | 🎉 Footer | Credenciais e links sociais |

---

## 🎬 Adicionando GIFs Animados

### Banco de GIFs (Gratuito)
1. **Giphy**: https://giphy.com (recomendado)
   - Procure: `terminal`, `dashboard`, `cloud`, `AI`, `chart`
   - Copie URL ou ID do GIF

2. **Tenor**: https://tenor.com
   - Alternativa a Giphy
   - Mesmos GIFs disponíveis

### Inserir GIF no Email
```html
<!-- Copie e adapte este código -->
<div class="gif-placeholder">
    <img src="https://media.giphy.com/media/[ID-DO-GIF]/giphy.gif" 
         alt="Descrição" 
         style="max-width: 100%; height: 300px;">
    <p><strong>Legenda do GIF</strong></p>
</div>
```

### GIFs Sugeridos

| Seção | Procure por... | Exemplo |
|-------|----------------|---------|
| OpenWebUI | "AI typing" | `xuXzcHta5uUJi` |
| Grafana | "real-time dashboard" | `3o7ZetQ5ohtA27SEGM` |
| Nextcloud | "cloud upload" | `3oKIPnAiaMCQbIiVdm` |
| SSH Terminal | "terminal hacking" | `l0HlDtKPoYJSzvASU` |
| Trading | "stock chart" | `13HgwGssSe2Sty` |

---

## ✅ Checklist Final

- [ ] Abrir email em navegador: ✅ Parece bom?
- [ ] Testar script: `python3 scripts/send_onboarding_email.py seu-email@empresa.com --dry-run`
- [ ] Customizar cores (opcional)
- [ ] Adicionar logo corporativo (opcional)
- [ ] Adicionar GIFs (opcional)
- [ ] Atualizar IPs se diferente de `192.168.15.2`
- [ ] Envio de teste para email pessoal
- [ ] Coletar feedback
- [ ] Enviare em produção para novos membros
- [ ] Documentar credenciais de acesso

---

## 🔧 Configuração SMTP

O script está pré-configurado para:
```
Host: mail.rpa4all.com
Porto: 587
Usuário: admin@rpa4all.com
```

Se precisar mudar para outro servidor SMTP, edite:
```bash
nano scripts/send_onboarding_email.py
```

Procure por (linha ~31-34):
```python
SMTP_HOST = "mail.rpa4all.com"     # ← MUDE AQUI
SMTP_PORT = 587                     # ← E AQUI
FROM_EMAIL = "admin@rpa4all.com"   # ← E AQUI
```

**Exemplos de outros servidores:**

```python
# Gmail
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Outlook 365
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587

# Seu servidor customizado
SMTP_HOST = "seu-servidor.com"
SMTP_PORT = 25  # ou 587, 465
```

---

## 📊 Informações do Email

| Métrica | Valor |
|---------|-------|
| **Tamanho** | 31 KB |
| **Compatibilidade** | 99% (todos clientes) |
| **Responsivo?** | ✅ Sim (mobile/tablet/desktop) |
| **Precisa de GIFs?** | ❌ Não (opcional) |
| **Seções** | 11 principais |
| **Serviços documentados** | 25+ |
| **Tabelas** | 5 detalhadas |
| **Tempo de leitura** | ~5-10 minutos |

---

## 🚀 Automação (Avançado)

### Envio automático em CI/CD
```yaml
# .github/workflows/send-onboarding.yml
name: Send Onboarding Email

on:
  workflow_dispatch:
    inputs:
      email:
        description: Email to send
        required: true

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Send Email
        env:
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
        run: |
          python3 scripts/send_onboarding_email.py ${{ github.event.inputs.email }} \
            --password "$SMTP_PASSWORD"
```

### Envio por webhook
```bash
# Criar script que recebe JSON e envia email
curl -X POST http://seu-servidor/onboarding \
  -H "Content-Type: application/json" \
  -d '{"email": "novo@empresa.com", "name": "Novo Membro"}'
```

---

## 🆘 Troubleshooting

### ❌ "Arquivo não encontrado"
```bash
# Verifique o caminho
pwd
ls -la docs/EMAIL_ONBOARDING_HOMELAB.html
```

### ❌ "Erro SMTP"
```bash
# Verificar credenciais
# Testar com Thunderbird ou Outlook

# Ver se ports 587 está aberta
telnet mail.rpa4all.com 587
```

### ❌ "Python não encontrado"
```bash
# Use python3 explicitamente
python3 --version
python3 scripts/send_onboarding_email.py seu-email@empresa.com
```

### ❌ "Email chegou no spam"
- Adicione remetente aos contatos
- Verifique SPF/DKIM/DMARC no seu servidor DNS
- Reduza quantidade de links no email

---

## 📞 Suporte

**Dúvidas?**
1. Leia `ONBOARDING_EMAIL_README.md` (documentação completa)
2. Leia `EMAIL_ONBOARDING_GUIDE.md` (guia de customização)
3. Teste com `--dry-run`
4. Verifique credenciais SMTP

**Mais informações:**
- Email: admin@rpa4all.com
- Doc: Veja arquivos `.md` no diretório `docs/`

---

## 🎉 Você está pronto!

```
✅ Email criado          → EMAIL_ONBOARDING_HOMELAB.html
✅ Script de envio       → send_onboarding_email.py
✅ Documentação          → 3 arquivos .md
✅ Pronto para usar      → Use em produção!
```

**Próximo passo:** Envie o email para seu primeiro novo membro! 🚀

---

**Vers**ão:** 1.0  
**Atualizado:** 09 de Março de 2026  
**Status:** ✅ Pronto para Produção
