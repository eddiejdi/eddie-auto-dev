#!/bin/bash
# =============================================================================
# Script de configuração do GitHub Agent
# =============================================================================

echo "🔧 Configuração do GitHub Agent"
echo "================================"

# Verifica se o token já está configurado
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✅ GITHUB_TOKEN já está configurado"
else
    echo ""
    echo "📝 Para usar o agente, você precisa de um token do GitHub."
    echo ""
    echo "Como criar um token:"
    echo "1. Acesse: https://github.com/settings/tokens"
    echo "2. Clique em 'Generate new token (classic)'"
    echo "3. Dê um nome ao token (ex: 'Ollama Agent')"
    echo "4. Selecione os escopos necessários:"
    echo "   - repo (acesso completo a repositórios privados)"
    echo "   - read:user (ler informações do usuário)"
    echo "   - read:org (ler organizações, opcional)"
    echo "5. Clique em 'Generate token' e copie o token"
    echo ""
    read -p "Cole seu GitHub Token aqui: " token
    
    if [ -n "$token" ]; then
        # Adiciona ao .bashrc
        echo "" >> ~/.bashrc
        echo "# GitHub Agent Token" >> ~/.bashrc
        echo "export GITHUB_TOKEN='$token'" >> ~/.bashrc
        
        # Exporta para a sessão atual
        export GITHUB_TOKEN="$token"
        
        echo "✅ Token configurado e salvo no ~/.bashrc"
    else
        echo "⚠️  Nenhum token fornecido. O agente terá acesso limitado."
    fi
fi

# Configurações do Ollama
echo ""
echo "📡 Configurações do Ollama"
echo "--------------------------"

OLLAMA_HOST=${OLLAMA_HOST:-"localhost"}
OLLAMA_PORT=${OLLAMA_PORT:-"11434"}
OLLAMA_MODEL=${OLLAMA_MODEL:-"codestral:22b"}

read -p "Host do Ollama [$OLLAMA_HOST]: " input_host
OLLAMA_HOST=${input_host:-$OLLAMA_HOST}

read -p "Porta do Ollama [$OLLAMA_PORT]: " input_port
OLLAMA_PORT=${input_port:-$OLLAMA_PORT}

read -p "Modelo do Ollama [$OLLAMA_MODEL]: " input_model
OLLAMA_MODEL=${input_model:-$OLLAMA_MODEL}

# Salva configurações
echo "" >> ~/.bashrc
echo "# Ollama Agent Config" >> ~/.bashrc
echo "export OLLAMA_HOST='$OLLAMA_HOST'" >> ~/.bashrc
echo "export OLLAMA_PORT='$OLLAMA_PORT'" >> ~/.bashrc
echo "export OLLAMA_MODEL='$OLLAMA_MODEL'" >> ~/.bashrc

export OLLAMA_HOST OLLAMA_PORT OLLAMA_MODEL

echo ""
echo "✅ Configurações salvas!"
echo ""
echo "📋 Resumo:"
echo "   OLLAMA_HOST: $OLLAMA_HOST"
echo "   OLLAMA_PORT: $OLLAMA_PORT"
echo "   OLLAMA_MODEL: $OLLAMA_MODEL"
echo "   GITHUB_TOKEN: ${GITHUB_TOKEN:+***configurado***}"
echo ""
echo "🚀 Para usar o agente, execute:"
echo "   python3 github_agent.py"
echo ""
echo "   Ou com comando direto:"
echo "   python3 github_agent.py 'liste meus repositórios'"
echo ""
