# 📅 Google Calendar Integration - Shared Assistant

Integração completa do Google Calendar com o Shared Assistant, permitindo criar, listar, editar e deletar eventos diretamente via Telegram e WhatsApp.

## ✨ Funcionalidades

### 📝 Gerenciamento de Eventos
- ✅ Criar eventos com linguagem natural
- ✅ Listar eventos por período (hoje, amanhã, semana, mês)
- ✅ Buscar eventos por texto
- ✅ Editar eventos existentes
- ✅ Deletar eventos
- ✅ Eventos recorrentes (diário, semanal, mensal, anual)
- ✅ Eventos de dia inteiro
- ✅ Adicionar participantes

### 🔔 Notificações Automáticas
- ✅ Lembretes configuráveis (30min, 10min, 5min antes)
- ✅ Agenda diária automática (manhã)
- ✅ Resumo semanal
- ✅ Notificações via Telegram E WhatsApp simultaneamente

### 🗣️ Linguagem Natural
O assistente entende comandos em português:
- "Agende uma reunião para amanhã às 14h"
- "O que tenho na agenda de hoje?"
- "Me lembre de ligar para o cliente às 10h"
- "Quais são meus compromissos da semana?"

## 🚀 Instalação

### 1. Dependências
```bash
pip install google-auth-oauthlib google-api-python-client python-dateutil
### 2. Configurar Credenciais Google

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione existente
3. Ative a **Google Calendar API**
4. Vá em **APIs e Serviços > Credenciais**
5. Clique em **Criar Credenciais > ID do cliente OAuth**
6. Selecione **Aplicativo para computador**
7. Baixe o JSON das credenciais
8. Salve como `calendar_data/credentials.json`

### 3. Autenticar
```bash
python setup_google_calendar.py
Ou via bot:
/calendar auth
## 📱 Comandos

### Telegram / WhatsApp

| Comando | Descrição |
|---------|-----------|
| `/calendar` | Ajuda completa |
| `/calendar auth` | Iniciar autenticação |
| `/calendar listar` | Eventos dos próximos 7 dias |
| `/calendar listar hoje` | Eventos de hoje |
| `/calendar listar amanhã` | Eventos de amanhã |
| `/calendar listar semana` | Próxima semana |
| `/calendar criar <texto>` | Criar evento |
| `/calendar buscar <termo>` | Buscar eventos |
| `/calendar livre` | Horários disponíveis |
| `/calendar deletar <id>` | Remover evento |
| `/calendar calendarios` | Listar calendários |

### Exemplos de Criação
/calendar criar Reunião com equipe amanhã às 14h
/calendar criar Consulta médica 25/01 às 10:00
/calendar criar Aniversário do João dia 15/02 dia inteiro
/calendar criar Standup diário às 9h semanal
### Linguagem Natural
Você também pode simplesmente digitar:
- "Agende uma reunião para quinta às 15h"
- "Me lembre de pagar conta amanhã às 10h"
- "O que tenho agendado para hoje?"
- "Cancele a reunião de amanhã"

## ⚙️ Serviço de Lembretes

### Instalar como Serviço
```bash
sudo cp shared-calendar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shared-calendar
sudo systemctl start shared-calendar
### Verificar Status
```bash
sudo systemctl status shared-calendar
journalctl -u shared-calendar -f
### Configurações (variáveis de ambiente)
```bash
# Lembretes (minutos antes do evento)
CALENDAR_REMINDER_MINUTES=30,10,5

# Hora do envio da agenda diária (0-23)
CALENDAR_DAILY_DIGEST_HOUR=7

# Dia da semana para resumo semanal (0=Segunda)
CALENDAR_WEEKLY_DIGEST_DAY=0
## 📂 Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `google_calendar_integration.py` | Módulo principal |
| `setup_google_calendar.py` | Script de setup |
| `calendar_reminder_service.py` | Serviço de lembretes |
| `shared-calendar.service` | Arquivo systemd |
| `calendar_data/` | Diretório de dados |
| `calendar_data/credentials.json` | Credenciais Google |
| `calendar_data/token.pickle` | Token de autenticação |

## 🔧 Arquitetura

┌─────────────────┐     ┌──────────────────────┐
│   Telegram Bot  │────▶│                      │
└─────────────────┘     │                      │
                        │  Google Calendar     │
┌─────────────────┐     │    Integration       │────▶ Google Calendar API
│  WhatsApp Bot   │────▶│                      │
└─────────────────┘     │                      │
                        └──────────────────────┘
                                  │
                                  ▼
                        ┌──────────────────────┐
                        │  Reminder Service    │
                        │  (Notificações)      │
                        └──────────────────────┘
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                   Telegram              WhatsApp
## 🔐 Segurança

- As credenciais são armazenadas localmente em `calendar_data/`
- O token OAuth2 é renovado automaticamente
- Apenas o admin pode usar comandos de gerenciamento
- As comunicações usam HTTPS

## 🐛 Troubleshooting

### Erro de autenticação
```bash
# Remover token antigo e reautenticar
rm calendar_data/token.pickle
python setup_google_calendar.py
### Lembretes não chegam
1. Verifique se o serviço está rodando:
   ```bash
   sudo systemctl status shared-calendar
   ```
2. Verifique os logs:
   ```bash
   cat /tmp/calendar_reminder.log
   ```
3. Confirme que WAHA API está acessível (WhatsApp)

### Eventos não são criados
1. Verifique autenticação: `/calendar auth`
2. Verifique permissões no Google Cloud Console
3. Teste com: `python setup_google_calendar.py`

## 📝 Changelog

### v1.0.0 (2026-01-10)
- ✅ Integração inicial com Google Calendar
- ✅ Suporte a Telegram e WhatsApp
- ✅ Criação de eventos com linguagem natural
- ✅ Sistema de lembretes automáticos
- ✅ Agenda diária e resumo semanal

## 🤝 Contribuição

Feito com ❤️ para o Shared Assistant.

---

**Shared Assistant** - Seu assistente pessoal inteligente 🤖
