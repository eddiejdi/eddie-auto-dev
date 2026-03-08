# 📧 Gmail Expurgo Inteligente v2.0

Sistema avançado de limpeza de emails com treinamento de IA e notificações inteligentes.

## 🚀 Funcionalidades

### 1. Limpeza Inteligente por Categoria
- **Promoções**: Emails > 30 dias
- **Social**: Emails > 60 dias
- **Updates**: Emails > 90 dias
- **Fóruns**: Emails > 60 dias
- **Spam**: Emails > 7 dias

### 2. Treinamento da IA Shared
Antes de excluir, o sistema:
- Analisa emails importantes
- Extrai conhecimento relevante
- Indexa no ChromaDB para busca semântica
- Treina modelos shared-* com o conteúdo

### 3. Lembretes Inteligentes
Extração automática de lembretes baseada em:
- Palavras-chave (urgente, prazo, reunião, pagamento)
- Datas mencionadas no email
- Análise de prioridade via IA
- Remetentes importantes

### 4. Notificações Multi-Canal
- **Telegram**: Relatórios e lembretes
- **WhatsApp**: Avisos via WAHA API
- Priorização de mensagens urgentes

## 📦 Instalação

```bash
# Executar script de instalação
chmod +x install_expurgo_inteligente.sh
sudo ./install_expurgo_inteligente.sh
### Pré-requisitos
- Python 3.8+
- Token Gmail configurado (`gmail_data/token.json`)
- Ollama rodando (para treinamento IA)
- WAHA rodando (para WhatsApp) - opcional
- Bot Telegram configurado - opcional

## ⚙️ Configuração

### Variáveis de Ambiente
Edite `.env.expurgo`:

```bash
OLLAMA_HOST=http://192.168.15.2:11434
WAHA_URL=http://localhost:3001
GMAIL_DATA_DIR=/home/homelab/myClaude/gmail_data
TELEGRAM_BOT_TOKEN=<store in tools/simple_vault/secrets and encrypt; do not commit plaintext>
ADMIN_CHAT_ID=seu_chat_id
ADMIN_PHONE=5511999999999
Note: We **store secrets encrypted** in `tools/simple_vault/secrets/` and deploy decrypted values to the homelab when needed. Example:

  printf '%s' '<telegram-bot-token>' | tools/simple_vault/add_secret.sh telegram_bot_token
  tools/simple_vault/decrypt_secret.sh tools/simple_vault/secrets/telegram_bot_token.gpg | sudo tee /etc/shared/telegram.env >/dev/null
  sudo chown root:root /etc/shared/telegram.env && sudo chmod 600 /etc/shared/telegram.env

For full guidance and best practices, see `docs/SECRETS.md`.

### Arquivo de Configuração
Edite `expurgo_config.json` para personalizar:
- Idade máxima por categoria
- Palavras-chave importantes
- Canais de notificação
- Agendamento

## 🎯 Uso

### Modo Simulação (Dry Run)
```bash
python3 gmail_expurgo_inteligente.py
Mostra o que seria feito sem executar.

### Executar de Verdade
```bash
python3 gmail_expurgo_inteligente.py --execute
### Modo Daemon (24/7)
```bash
python3 gmail_expurgo_inteligente.py --execute --daemon --interval 24
### Opções Completas
```bash
python3 gmail_expurgo_inteligente.py --help

Opções:
  --execute          Executar de verdade (não dry run)
  --daemon           Executar como daemon
  --interval HORAS   Intervalo em horas (default: 24)
  --channels         Canais: telegram whatsapp
  --no-notifications Desabilitar notificações
  --no-training      Desabilitar treinamento IA
## 🔧 Serviço Systemd

### Instalar
```bash
sudo cp shared-expurgo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shared-expurgo
### Gerenciar
```bash
sudo systemctl start shared-expurgo   # Iniciar
sudo systemctl stop shared-expurgo    # Parar
sudo systemctl status shared-expurgo  # Status
journalctl -u shared-expurgo -f       # Logs
## 📊 Relatórios

### Exemplo de Relatório
📊 Relatório Expurgo Inteligente
_11/01/2026 14:30_

Modo: EXECUÇÃO

📁 Por Categoria:
✅ PROMOTIONS: 245 (>30d)
✅ SOCIAL: 123 (>60d)
✅ UPDATES: 89 (>90d)
⚪ FORUMS: 0 (>60d)
✅ SPAM: 45 (>7d)

📈 Totais:
• Analisados: 502
• Movidos p/ lixeira: 502
• Treinados na IA: 47
• Lembretes criados: 5

🧠 Base de Conhecimento:
• Emails indexados: 1,234
• ChromaDB: ✅
## 🔔 Lembretes Inteligentes

### Tipos de Lembretes
- 🔵 **LOW**: Informativo
- 🟢 **NORMAL**: Atenção moderada
- 🟠 **HIGH**: Importante
- 🔴 **URGENT**: Ação imediata

### Exemplo de Lembrete
🔔 Lembrete Inteligente 🟠

*Reunião de Revisão do Projeto*

📋 Confirmar presença na reunião de revisão
do projeto XYZ amanhã às 14h.

📧 Origem: Re: Agendamento reunião projeto...
📅 Data: 12/01/2026 14:00

⚡ Ação necessária!

🏷️ Tags: reunião, confirmar, projeto
## 🧠 Treinamento da IA

### Como Funciona
1. Emails importantes são identificados por:
   - Labels (IMPORTANT, STARRED)
   - Palavras-chave (projeto, código, deploy)
   - Score de spam negativo

2. Conhecimento extraído:
   - Assunto e remetente
   - Conteúdo principal
   - Data e contexto

3. Indexação:
   - Embeddings via Ollama (nomic-embed-text)
   - Armazenamento no ChromaDB
   - Busca semântica posterior

### Buscar Emails Treinados
from email_trainer import get_email_trainer

trainer = get_email_trainer()
results = trainer.search_emails("reunião projeto python", n_results=5)
## 🔌 Integração com Outros Módulos

### Gmail Integration
from gmail_expurgo_inteligente import ExpurgoInteligente

expurgo = ExpurgoInteligente()
result = await expurgo.run_expurgo(dry_run=False)
### Telegram Bot
O bot pode chamar o expurgo:
/expurgo analisar - Relatório
/expurgo executar - Executar limpeza
/expurgo stats    - Estatísticas
### API de Notificação
from gmail_expurgo_inteligente import NotificationService

notifier = NotificationService()
await notifier.notify("Mensagem teste", NotificationType.INFO)
## 📈 Estatísticas

### Ver Estatísticas
from gmail_expurgo_inteligente import ExpurgoInteligente

expurgo = ExpurgoInteligente()
print(expurgo.stats)
### Logs
```bash
tail -f /var/log/shared-expurgo.log
## 🐛 Troubleshooting

### Gmail não conecta
```bash
# Verificar token
cat /home/homelab/myClaude/gmail_data/token.json

# Renovar autenticação
python3 gmail_oauth_local.py
### Telegram não envia
```bash
# Testar API
curl "https://api.telegram.org/bot$BOT_TOKEN/getMe"
### WhatsApp não envia
```bash
# Verificar WAHA
curl http://localhost:3001/api/sessions
### Ollama não treina
```bash
# Verificar Ollama
curl http://192.168.15.2:11434/api/tags
## 📁 Arquivos

myClaude/
├── gmail_expurgo_inteligente.py   # Script principal
├── email_trainer.py               # Módulo de treinamento
├── expurgo_config.json            # Configuração
├── shared-expurgo.service          # Serviço systemd
├── install_expurgo_inteligente.sh # Instalação
├── .env.expurgo                   # Variáveis ambiente
├── gmail_data/
│   └── token.json                 # Token Gmail
├── chroma_db/                     # Base ChromaDB
└── email_training_data/           # Dados treinamento
## 📄 Licença

MIT License - Shared Assistant 2026
