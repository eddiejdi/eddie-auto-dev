#!/bin/bash
# Script para remover usuário shared do servidor
# Execute como root: sudo bash remove_shared_user.sh

echo "🔍 Verificando usuário shared..."
if id "shared" &>/dev/null; then
    echo "⚠️  Usuário shared encontrado!"
    
    # 1. Parar serviços que usam shared
    echo "🛑 Parando serviços..."
    sudo systemctl stop shared-telegram-bot 2>/dev/null
    sudo systemctl stop shared-whatsapp-bot 2>/dev/null
    sudo systemctl stop shared-calendar 2>/dev/null
    sudo systemctl stop github-agent 2>/dev/null
    sudo systemctl stop specialized-agents 2>/dev/null
    sudo systemctl stop specialized-agents-api 2>/dev/null
    sudo systemctl stop btc-trading-agent 2>/dev/null
    sudo systemctl stop btc-trading-engine 2>/dev/null
    
    # 2. Mover dados importantes para homelab (se existirem)
    echo "📦 Movendo dados importantes..."
    if [ -d "/home/shared/myClaude" ] && [ ! -d "/home/homelab/myClaude" ]; then
        sudo mv /home/shared/myClaude /home/homelab/
        sudo chown -R homelab:homelab /home/homelab/myClaude
    elif [ -d "/home/shared/myClaude" ]; then
        echo "⚠️  /home/homelab/myClaude já existe, fazendo backup..."
        sudo mv /home/shared/myClaude /home/shared/myClaude.bak
    fi
    
    # 3. Mover outros arquivos importantes
    if [ -d "/home/shared/.ssh" ]; then
        sudo cp -r /home/shared/.ssh/* /home/homelab/.ssh/ 2>/dev/null
        sudo chown -R homelab:homelab /home/homelab/.ssh
    fi
    
    # 4. Remover usuário shared
    echo "🗑️  Removendo usuário shared..."
    sudo userdel -r shared 2>/dev/null || sudo userdel shared
    
    echo "✅ Usuário shared removido!"
    
    # 5. Verificar
    if id "shared" &>/dev/null; then
        echo "❌ Erro: usuário shared ainda existe"
    else
        echo "✅ Confirmado: usuário shared não existe mais"
    fi
    
    # 6. Atualizar serviços
    echo "🔄 Recarregando serviços..."
    sudo systemctl daemon-reload
    
    # 7. Reiniciar serviços
    echo "🚀 Reiniciando serviços..."
    sudo systemctl start shared-telegram-bot 2>/dev/null
    sudo systemctl start shared-whatsapp-bot 2>/dev/null
    sudo systemctl start shared-calendar 2>/dev/null
    sudo systemctl start specialized-agents-api 2>/dev/null
    
else
    echo "✅ Usuário shared não existe no sistema"
fi

echo ""
echo "📋 Usuários do sistema:"
cat /etc/passwd | grep -E "homelab|shared" || echo "Nenhum usuário shared/homelab"
