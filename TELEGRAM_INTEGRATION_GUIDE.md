# 📱 Alertmanager → Telegram Integration

> **Objetivo**: Receber alertas de Self-Healing do Prometheus no Telegram em tempo real

---

## 🚀 Quick Start

### Pré-requisitos
1. Bot do Telegram criado e token obtido
2. Chat ID do grupo/channel obtido
3. SSH access ao homelab

### Deploy (Uma linha!)
```bash
# Export suas credenciais
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklmNOPqrs"
export TELEGRAM_CHAT_ID="987654321"

# Execute o deploy
./deploy_alertmanager_telegram.sh homelab 192.168.15.2
```

**Pronto!** Notificações agora serão enviadas ao seu Telegram automaticamente.

---

## 📝 Como Obter Credenciais do Telegram

### Passo 1: Criar um Bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Digite `/start`
3. Digite `/newbot`
4. BotFather vai pedir:
   - **Nome do bot**: ex: `EddieAutoDevBot`
   - **Username do bot**: ex: `EddieAutoDevBot` (sem espaços)
5. Você receberá uma mensagem como:
   ```
   Done! Congratulations on your new bot. 
   You will find it at t.me/EddieAutoDevBot. 
   You can now add a description, about section and profile picture for your bot.
   
   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklmNOPqrs  ← COPIE ISSO!
   ```

**Copie o token** (formato: `123456789:ABCdefGHIjklmNOPqrs`)

### Passo 2: Criar um Grupo ou Channel

**Opção A: Usar um Grupo Privado (Recomendado)**
1. Abra Telegram
2. Clique em ➕ (novo chat) → Novo Grupo
3. Nome: `Eddie Auto Dev - Alerts`
4. Adicione seu bot (@EddieAutoDevBot) ao grupo
5. Convide você mesmo ao grupo (já estará lá)

**Opção B: Usar um Channel**
1. Telegram → ➕ (novo chat) → Novo Canal
2. Nome: `Eddie Auto Dev Alerts`
3. Tipo: **Privado**
4. Adicione seu bot como admin

### Passo 3: Obter Chat ID

**Forma A: Usando @userinfobot (Fácil)**
1. Procure por **@userinfobot**
2. Envie `/start`
3. A resposta mostra seu ID pessoal
4. Se for um grupo, adicione @userinfobot ao grupo:
   - Ele enviará uma mensagem com o Chat ID do grupo
   - Formato: `-123456789` (com hífen!)

**Forma B: Via Bot do Telegram (Avançado)**
```bash
# Envie uma mensagem para seu grupo/canal
# Depois execute:
curl "https://api.telegram.org/botTOKEN/getUpdates" | jq '.result[-1].message.chat.id'
# Substitua TOKEN pelo seu bot token
```

**Forma C: Procurar na URL**
1. Abra seu grupo/channel
2. Procure pela URL:
   - Grupo privado: `t.me/c/123456789/1` → Chat ID: `-100123456789`
   - Channel: URL mostra no navegador

---

## 🔧 Deploy Manual (Se Quiser Entender Tudo)

### Step 1: Transferir Scripts
```bash
scp tools/alerting/alertmanager_telegram_webhook.py homelab@192.168.15.2:/tmp/
scp tools/alerting/alertmanager_telegram.yml homelab@192.168.15.2:/tmp/
```

### Step 2: Instalar Webhook Receiver
```bash
ssh homelab@192.168.15.2 << 'EOF'
sudo mv /tmp/alertmanager_telegram_webhook.py /usr/local/bin/
sudo chmod +x /usr/local/bin/alertmanager_telegram_webhook.py

# Instalar dependências Python
pip3 install bottle requests
EOF
```

### Step 3: Criar Systemd Service
```bash
ssh homelab@192.168.15.2 << 'EOF'
sudo tee /etc/systemd/system/alertmanager-telegram-webhook.service > /dev/null << 'SERVICE'
[Unit]
Description=Alertmanager → Telegram Webhook
After=network.target
Wants=alertmanager.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/alertmanager_telegram_webhook.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment="TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmNOPqrs"
Environment="TELEGRAM_CHAT_ID=-123456789"
Environment="WEBHOOK_PORT=5000"

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable alertmanager-telegram-webhook.service
sudo systemctl start alertmanager-telegram-webhook.service
EOF
```

### Step 4: Instalar Configuração Alertmanager
```bash
ssh homelab@192.168.15.2 << 'EOF'
sudo cp /etc/prometheus/alertmanager.yml /etc/prometheus/alertmanager.yml.backup
sudo cp /tmp/alertmanager_telegram.yml /etc/prometheus/alertmanager.yml
sudo chown root:root /etc/prometheus/alertmanager.yml
sudo chmod 644 /etc/prometheus/alertmanager.yml
sudo systemctl reload alertmanager
EOF
```

---

## ✅ Verificação

### Verificar se Webhook está Rodando
```bash
ssh homelab@192.168.15.2 "curl -s http://localhost:5000/health | jq"
# Expected output:
# {
#   "status": "ok",
#   "timestamp": "2026-02-28T15:30:00.123456"
# }
```

### Verificar Serviços
```bash
ssh homelab@192.168.15.2 "sudo systemctl status alertmanager alertmanager-telegram-webhook --no-pager"
# Expected: both active (running)
```

### Ver Logs
```bash
# Logs do webhook
ssh homelab@192.168.15.2 "sudo journalctl -u alertmanager-telegram-webhook -f"

# Logs do Alertmanager
ssh homelab@192.168.15.2 "sudo journalctl -u alertmanager -f"
```

---

## 🧪 Teste Manual

### Enviar Alerta de Teste

```bash
# Via Alertmanager API
ssh homelab@192.168.15.2 << 'EOF'
curl -X POST http://localhost:9093/api/v1/alerts \
  -H 'Content-Type: application/json' \
  -d '[
    {
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Teste de Alerta - Verificando Telegram",
        "description": "Este é um alerta de teste para validar integração com Telegram"
      },
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }
  ]'
EOF
```

Se tudo estiver OK, você receberá uma mensagem no Telegram com:
```
🔴 ALERTA - FIRING

Nome: TestAlert
Severidade: CRITICAL
Hora: 15:30:45

Resumo:
Teste de Alerta - Verificando Telegram

Detalhes:
Este é um alerta de teste para validar integração com Telegram
```

---

## 🎯 Configuração de Alertas

Os alertas de Self-Healing são configurados em: [monitoring/prometheus/selfhealing_rules.yml](../monitoring/prometheus/selfhealing_rules.yml)

### Alertas que Disparam Notificação Telegram

| Alerta | Severidade | Quando |
|--------|-----------|--------|
| `OllamaFrozen` | critical | Ollama travado > 180s |
| `OllamaSlowResponse` | warning | Resposta lenta > 5s |
| `OllamaMemoryPressure` | warning | VRAM > 90% |
| `ServiceStalled` | critical | Serviço travado > 300s |
| `SelfHealingExhausted` | warning | > 3 restarts/hora |
| `ConsecutiveFailures` | critical | > 2 falhas consecutivas |

---

## 🚨 Troubleshooting

### "Webhook não está respondendo"
```bash
# Verificar se processo está rodando
ssh homelab@192.168.15.2 "ps aux | grep alertmanager_telegram_webhook"

# Verificar se porta está aberta
ssh homelab@192.168.15.2 "sudo netstat -tlnp | grep 5000"

# Reinstalar:
./deploy_alertmanager_telegram.sh homelab 192.168.15.2
```

### "Mensagens não chegam ao Telegram"
```bash
# Verificar credenciais
echo "Bot Token: $TELEGRAM_BOT_TOKEN"
echo "Chat ID: $TELEGRAM_CHAT_ID"

# Testar API do Telegram diretamente
curl "https://api.telegram.org/botTOKEN/getMe" | jq
# Substitua TOKEN pelo seu bot token
# Expected: "ok": true

# Ver logs do webhook
ssh homelab@192.168.15.2 "sudo journalctl -u alertmanager-telegram-webhook -n 50"
```

### "Chat ID está incorreto"
Os IDs de grupo começam com **hífen** (`-`):
- Chat ID correto: `-123456789`
- Chat ID INCORRETO: `123456789` ou `-100123456789` (channel)

Se for channel privado, o ID é: `-100123456789`

---

## 📊 Fluxo Completo

```
Prometheus
    ↓
Detecta alerta (ex: OllamaFrozen)
    ↓
Alertmanager
    ↓
Verifica routes (selfhealing/critical)
    ↓
Envia webhook POST para http://localhost:5000/alerts
    ↓
alertmanager_telegram_webhook.py recebe
    ↓
Formata mensagem em HTML
    ↓
Envia via Telegram Bot API
    ↓
📱 Mensagem chega no seu grupo/channel!
```

---

## 🔐 Segurança

⚠️ **Notas Importantes**:
- **Nunca commit seu bot token** no git
- Use **variáveis de ambiente** ou **secrets do GitHub**
- Bot tokens são como senhas — mantenha seguro
- Se expor acidentalmente, recriar o bot em @BotFather

Para GitHub Actions:
```bash
# Adicionar ao GitHub Secrets:
# Settings → Secrets and variables → Actions
# TELEGRAM_BOT_TOKEN: seu/bot/token
# TELEGRAM_CHAT_ID: seu-chat-id
```

---

## 📚 Referência

- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Webhook Documentation](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)

---

**Criado**: 2026-02-28
**Última atualização**: 2026-02-28
