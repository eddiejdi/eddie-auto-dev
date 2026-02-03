# 📱 Telegram - Setup Automatizado do Cofre

**Status:** 🟡 Parcialmente Configurado  
**Chat ID:** ✅ 948686300 (já conhecido)  
**Token:** ⚠️ Pendente (preencher do @BotFather)

---

## ✅ O que foi encontrado e configurado:

### 1. Chat ID - PRONTO ✅
```
948686300
```

**Fonte:** Encontrado em múltiplos arquivos do projeto:
- `telegram_bot.py`: `ADMIN_CHAT_ID = 948686300`
- `calendar_reminder_service.py`
- `delivery_approval.py`
- `github_agent_streamlit.py`
- `gmail_expurgo_inteligente.py`

**Já configurado em:**
- ✅ `~/.telegram_config.json` (campo `chat_id`)
- ✅ Script pronto para criar em Bitwarden

---

### 2. Token - PENDENTE ⚠️

**Localização atual:** Encriptado no simple_vault
- `tools/simple_vault/secrets/telegram_bot_token.gpg`
- ❌ Não foi possível descriptografar (passphrase incorreta)

**Estrutura de carregamento (já implementada):**
```python
# tools/secrets_loader.py
def get_telegram_token():
    candidates = [
        "eddie/telegram_bot_token",    # ← Nome correto para Bitwarden
        "telegram_bot_token",
        "telegram/bot_token",
    ]
    # Busca via get_field() do vault
```

**Usado por 15+ scripts:**
- `telegram_bot.py` (bot principal)
- `validation_scheduler.py` (alertas RPA4ALL)
- `google_calendar_integration.py`
- `dashboard/config.py`
- `github_agent_streamlit.py`
- E mais...

---

## 🔧 Arquivos Criados/Configurados:

| Arquivo | Status | Conteúdo |
|---------|--------|----------|
| `~/.telegram_config.json` | ✅ Criado | Chat ID: 948686300<br>Token: PENDENTE |
| `/tmp/create_telegram_items_bw.sh` | ✅ Pronto | Script para criar items no Bitwarden |
| Bitwarden items | 🟡 Pendente | Aguarda execução do script |

---

## 🚀 Próximos Passos:

### Opção 1: Via @BotFather (Recomendado - Novo Token)

```bash
# 1. Obter novo token
# - Abra Telegram
# - Converse com @BotFather
# - Envie: /newbot
# - Escolha nome: "Eddie RPA4ALL Monitoring"
# - Escolha username: "eddie_rpa4all_bot" (ou similar)
# - COPIE O TOKEN (formato: 1234567890:ABCdef...)

# 2. Configurar localmente
nano ~/.telegram_config.json
# Cole o token no campo "token"

# 3. Salvar no Bitwarden
bash /tmp/create_telegram_items_bw.sh
# Depois edite o item 'eddie/telegram_bot_token' no Bitwarden
# E cole o token real
```

---

### Opção 2: Recuperar Token Existente (se houver acesso)

Se você tem acesso ao bot original que gera as mensagens para 948686300:

```bash
# No Telegram, envie para @BotFather:
/mybots
# Selecione o bot Eddie
# API Token → Copie o token

# Configure:
nano ~/.telegram_config.json
# Cole o token

# Salve no Bitwarden:
bash /tmp/create_telegram_items_bw.sh
```

---

## 🧪 Teste de Conexão:

Após configurar o token:

```bash
# Teste 1: Validação manual
python3 -c "
import json
from pathlib import Path
config = json.loads(Path.home().joinpath('.telegram_config.json').read_text())
print(f\"✅ Chat ID: {config['chat_id']}\")
print(f\"✅ Token: {config['token'][:20]}...\")
"

# Teste 2: Enviar mensagem via validation_scheduler
python3 validation_scheduler.py https://www.rpa4all.com/

# Teste 3: Enviar via bot principal
python3 -c "
import sys
sys.path.insert(0, '/home/edenilson/eddie-auto-dev')
from tools.secrets_loader import get_telegram_token, get_telegram_chat_id
import urllib.request, json

token = get_telegram_token()
chat_id = get_telegram_chat_id()

url = f'https://api.telegram.org/bot{token}/sendMessage'
data = json.dumps({'chat_id': chat_id, 'text': '✅ Telegram configurado!'}).encode()
req = urllib.request.Request(url, data, {'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
print('✅ Mensagem enviada!')
"
```

---

## 📊 Estrutura do Bitwarden (após configuração):

```
eddie/telegram_bot_token
├── Type: Secure Note
├── Fields:
│   └── password: <TOKEN_DO_BOTFATHER>
└── Notes: "Token do bot Eddie para alertas..."

eddie/telegram_chat_id
├── Type: Secure Note
├── Fields:
│   └── password: 948686300
└── Notes: "Chat ID do administrador Eddie..."
```

---

## 🔍 Como funciona a integração:

```python
# 1. validation_scheduler.py carrega de ~/.telegram_config.json
config = json.loads(Path.home().joinpath('.telegram_config.json').read_text())
token = config['token']
chat_id = config['chat_id']

# 2. telegram_bot.py e outros usam secrets_loader
from tools.secrets_loader import get_telegram_token, get_telegram_chat_id
token = get_telegram_token()  # Busca no Bitwarden: eddie/telegram_bot_token
chat_id = get_telegram_chat_id()  # Variável de ambiente ou Bitwarden
```

**Ambos os métodos devem funcionar após configuração completa.**

---

## 🎯 Resumo Executivo:

| Item | Status | Ação Necessária |
|------|--------|-----------------|
| Chat ID | ✅ Configurado | Nenhuma (948686300) |
| Token local | 🟡 Template | Editar `~/.telegram_config.json` |
| Token Bitwarden | 🟡 Pendente | Executar script + editar item |
| Teste de conexão | ⏳ Aguardando | Após preencher token |

---

## ⚠️ Nota Importante:

O token atual está encriptado no simple_vault mas **não foi possível descriptografar** com a passphrase local. Isso significa que:

1. **Opção A:** Você tem o token em outro lugar (Telegram, backup, outra máquina)
2. **Opção B:** Criar um novo bot no @BotFather (mais simples e rápido)

**Recomendação:** Criar novo bot (5 minutos) ao invés de tentar recuperar token antigo.

---

**Última atualização:** 02/02/2026  
**Gerado por:** GitHub Copilot  
**Baseado em:** Análise de 50+ arquivos e credenciais do projeto
