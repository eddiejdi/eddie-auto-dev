#!/bin/bash
# Script para remover usuário eddie do servidor
# Execute como root: sudo bash remove_eddie_user.sh

echo "🔍 Verificando usuário eddie..."
if id "eddie" &>/dev/null; then
    echo "⚠️  Usuário eddie encontrado!"
    
    # 1. Parar serviços que usam eddie
    echo "🛑 Parando serviços..."
    sudo systemctl stop eddie-telegram-bot 2>/dev/null
    sudo systemctl stop eddie-whatsapp-bot 2>/dev/null
    sudo systemctl stop eddie-calendar 2>/dev/null
    sudo systemctl stop github-agent 2>/dev/null
    sudo systemctl stop specialized-agents 2>/dev/null
    sudo systemctl stop specialized-agents-api 2>/dev/null
    sudo systemctl stop btc-trading-agent 2>/dev/null
    sudo systemctl stop btc-trading-engine 2>/dev/null
    
    # 2. Mover dados importantes para homelab (se existirem)
    echo "📦 Movendo dados importantes..."
    if [ -d "/home/eddie/myClaude" ] && [ ! -d "/home/homelab/myClaude" ]; then
        sudo mv /home/eddie/myClaude /home/homelab/
        sudo chown -R homelab:homelab /home/homelab/myClaude
    elif [ -d "/home/eddie/myClaude" ]; then
        echo "⚠️  /home/homelab/myClaude já existe, fazendo backup..."
        sudo mv /home/eddie/myClaude /home/eddie/myClaude.bak
    fi
    
    # 3. Mover outros arquivos importantes
    if [ -d "/home/eddie/.ssh" ]; then
        sudo cp -r /home/eddie/.ssh/* /home/homelab/.ssh/ 2>/dev/null
        sudo chown -R homelab:homelab /home/homelab/.ssh
    fi
    
    # 4. Remover usuário eddie
    echo "🗑️  Removendo usuário eddie..."
    sudo userdel -r eddie 2>/dev/null || sudo userdel eddie
    
    echo "✅ Usuário eddie removido!"
    
    # 5. Verificar
    if id "eddie" &>/dev/null; then
        echo "❌ Erro: usuário eddie ainda existe"
    else
        echo "✅ Confirmado: usuário eddie não existe mais"
    fi
    
    # 6. Atualizar serviços
    echo "🔄 Recarregando serviços..."
    sudo systemctl daemon-reload
    
    # 7. Reiniciar serviços
    echo "🚀 Reiniciando serviços..."
    sudo systemctl start eddie-telegram-bot 2>/dev/null
    sudo systemctl start eddie-whatsapp-bot 2>/dev/null
    sudo systemctl start eddie-calendar 2>/dev/null
    sudo systemctl start specialized-agents-api 2>/dev/null
    
else
    echo "✅ Usuário eddie não existe no sistema"
fi

echo ""
echo "📋 Usuários do sistema:"
cat /etc/passwd | grep -E "homelab|eddie" || echo "Nenhum usuário eddie/homelab"
