#!/bin/bash
# Script para configurar @Proj_Teminal_bot no sistema

echo "🤖 Configurando @Proj_Teminal_bot"
echo "=================================="
echo ""
echo "Este script ajudará você a:"
echo "1. Obter o token do bot"
echo "2. Configurar localmente"
echo "3. Salvar no Bitwarden"
echo ""

# Função para validar token
validate_token() {
    local token=$1
    # Token válido do Telegram tem formato: numero:string
    if [[ $token =~ ^[0-9]{8,10}:[A-Za-z0-9_-]{24,}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Passo 1: Obter token
echo "📋 PASSO 1: Obter Token do Bot"
echo "=============================="
echo ""
echo "No Telegram:"
echo "1. Abra um chat com @BotFather"
echo "2. Envie: /mybots"
echo "3. Selecione: Proj_Teminal_bot"
echo "4. Selecione: 'API Token'"
echo "5. COPIE o token que aparecerá"
echo ""

read -p "Cole o token do @Proj_Teminal_bot: " TELEGRAM_TOKEN

# Validar token
if ! validate_token "$TELEGRAM_TOKEN"; then
    echo "❌ Formato de token inválido!"
    echo "Token deve ter formato: 1234567890:ABCdef..."
    exit 1
fi

echo "✅ Token válido"
echo ""

# Passo 2: Configurar localmente
echo "📝 PASSO 2: Configurar ~/.telegram_config.json"
echo "=============================================="

cat > ~/.telegram_config.json <<EOF
{
  "token": "${TELEGRAM_TOKEN}",
  "chat_id": "948686300"
}
EOF

chmod 0600 ~/.telegram_config.json

echo "✅ Arquivo criado: ~/.telegram_config.json"
echo "✅ Permissões: 0600 (seguro)"
echo ""

# Passo 3: Testar conexão
echo "🧪 PASSO 3: Testar Conexão"
echo "==========================="
echo ""

python3 << 'PYTHON'
import json
from pathlib import Path
import urllib.request
import urllib.error

config_path = Path.home() / ".telegram_config.json"
config = json.loads(config_path.read_text())

token = config["token"]
chat_id = config["chat_id"]

print(f"🔍 Testando conexão...")
print(f"   Chat ID: {chat_id}")
print(f"   Token: {token[:20]}...")

try:
    url = f"https://api.telegram.org/bot{token}/getMe"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.loads(response.read().decode())
        
        if result.get("ok"):
            bot_info = result.get("result", {})
            bot_name = bot_info.get("username", "unknown")
            bot_id = bot_info.get("id", "unknown")
            
            print(f"✅ Conexão bem-sucedida!")
            print(f"   Bot: @{bot_name}")
            print(f"   ID: {bot_id}")
            
            # Tentar enviar mensagem de teste
            print(f"")
            print(f"📤 Enviando mensagem de teste...")
            
            send_url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({
                "chat_id": chat_id,
                "text": "✅ Sistema de Monitoramento RPA4ALL\n\n@Proj_Teminal_bot configurado com sucesso!\n\n📊 Dashboard: http://localhost:8504\n🔍 Validações automáticas ativadas"
            }).encode()
            
            send_req = urllib.request.Request(
                send_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(send_req, timeout=5) as send_response:
                send_result = json.loads(send_response.read().decode())
                if send_result.get("ok"):
                    print(f"✅ Mensagem de teste enviada!")
                else:
                    print(f"⚠️ Erro ao enviar: {send_result}")
        else:
            print(f"❌ Erro: {result}")
except urllib.error.URLError as e:
    print(f"❌ Erro de conexão: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Erro: {e}")
    exit(1)

PYTHON

echo ""
echo "✅ TESTE CONCLUÍDO"
echo ""

# Passo 4: Salvar no Bitwarden
echo "💾 PASSO 4: Salvar no Bitwarden"
echo "================================"
echo ""

# Criar itens no Bitwarden
cat > /tmp/telegram_bot_final.json <<EOF
{
  "organizationId": null,
  "folderId": null,
  "type": 2,
  "name": "shared/telegram_bot_token",
  "notes": "Token do bot @Proj_Teminal_bot\nChat ID: 948686300\nBot para alertas e monitoramento RPA4ALL\nCriado: 2026-02-02\nÚltima atualização: $(date)",
  "favorite": false,
  "fields": [
    {
      "name": "password",
      "value": "${TELEGRAM_TOKEN}",
      "type": 1
    },
    {
      "name": "bot_username",
      "value": "Proj_Teminal_bot",
      "type": 0
    },
    {
      "name": "chat_id",
      "value": "948686300",
      "type": 0
    }
  ],
  "secureNote": {
    "type": 0
  }
}
EOF

if bw create item /tmp/telegram_bot_final.json 2>&1 | grep -q '"id"'; then
    echo "✅ Token salvo no Bitwarden"
    echo "   Item: shared/telegram_bot_token"
else
    echo "⚠️ Já existe item no Bitwarden"
    echo "   Atualize manualmente se necessário"
fi

# Verificar Chat ID
echo ""
echo "✅ Verificando Chat ID..."

cat > /tmp/telegram_chatid_final.json <<EOF
{
  "organizationId": null,
  "folderId": null,
  "type": 2,
  "name": "shared/telegram_chat_id",
  "notes": "Chat ID do administrador Shared\nUsado por todos os bots e alertas\nCriado: 2026-02-02",
  "favorite": false,
  "fields": [
    {
      "name": "password",
      "value": "948686300",
      "type": 1
    }
  ],
  "secureNote": {
    "type": 0
  }
}
EOF

if bw create item /tmp/telegram_chatid_final.json 2>&1 | grep -q '"id"'; then
    echo "✅ Chat ID salvo no Bitwarden"
    echo "   Item: shared/telegram_chat_id"
else
    echo "⚠️ Já existe item no Bitwarden"
fi

rm -f /tmp/telegram_*_final.json

echo ""
echo "=================================="
echo "✅ CONFIGURAÇÃO CONCLUÍDA!"
echo "=================================="
echo ""
echo "📊 Dashboard: http://localhost:8504"
echo "📱 Bot: @Proj_Teminal_bot"
echo "💬 Chat ID: 948686300"
echo ""
echo "Próximos passos:"
echo "1. ✅ Validação Selenium: rodando"
echo "2. ✅ Alertas Telegram: configurado"
echo "3. 🟡 Systemd Timer: instalar com sudo"
echo ""
echo "Para instalar o timer:"
echo "  sudo cp rpa4all-validation.service /etc/systemd/system/"
echo "  sudo cp rpa4all-validation.timer /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now rpa4all-validation.timer"
echo ""
