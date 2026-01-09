#!/bin/bash
# =============================================================================
# Script de instalação e execução do GitHub Agent Server
# =============================================================================

echo "🚀 GitHub Agent Server - Instalação"
echo "===================================="

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instalando..."
    sudo apt update && sudo apt install -y python3 python3-pip
fi

# Instala dependências
echo ""
echo "📦 Instalando dependências Python..."
pip3 install flask flask-cors requests --quiet

# Configuração do OAuth (opcional)
echo ""
echo "🔐 Configuração do GitHub OAuth (opcional)"
echo "----------------------------------------"
echo "O OAuth permite login com um clique, mas requer criar um GitHub App."
echo ""
echo "Para criar um OAuth App:"
echo "1. Acesse: https://github.com/settings/developers"
echo "2. Clique em 'OAuth Apps' -> 'New OAuth App'"
echo "3. Preencha:"
echo "   - Application name: GitHub Agent"
echo "   - Homepage URL: http://localhost:5000"
echo "   - Authorization callback URL: http://localhost:5000/callback"
echo ""

read -p "Deseja configurar OAuth agora? (s/n) [n]: " setup_oauth

if [[ "$setup_oauth" == "s" || "$setup_oauth" == "S" ]]; then
    read -p "Client ID: " client_id
    read -p "Client Secret: " client_secret
    
    if [[ -n "$client_id" && -n "$client_secret" ]]; then
        # Salva no .bashrc
        echo "" >> ~/.bashrc
        echo "# GitHub OAuth" >> ~/.bashrc
        echo "export GITHUB_CLIENT_ID='$client_id'" >> ~/.bashrc
        echo "export GITHUB_CLIENT_SECRET='$client_secret'" >> ~/.bashrc
        echo "export GITHUB_REDIRECT_URI='http://localhost:5000/callback'" >> ~/.bashrc
        
        export GITHUB_CLIENT_ID="$client_id"
        export GITHUB_CLIENT_SECRET="$client_secret"
        export GITHUB_REDIRECT_URI="http://localhost:5000/callback"
        
        echo "✅ OAuth configurado!"
    fi
else
    echo "⏭️  OAuth ignorado. Você pode usar login com token."
fi

# Configuração do Ollama
echo ""
echo "📡 Configuração do Ollama"
echo "-------------------------"

OLLAMA_HOST=${OLLAMA_HOST:-"192.168.15.2"}
OLLAMA_PORT=${OLLAMA_PORT:-"11434"}
OLLAMA_MODEL=${OLLAMA_MODEL:-"codestral:22b"}

read -p "Host do Ollama [$OLLAMA_HOST]: " input_host
OLLAMA_HOST=${input_host:-$OLLAMA_HOST}

read -p "Modelo [$OLLAMA_MODEL]: " input_model
OLLAMA_MODEL=${input_model:-$OLLAMA_MODEL}

# Salva configurações
echo "" >> ~/.bashrc
echo "# Ollama Config" >> ~/.bashrc
echo "export OLLAMA_HOST='$OLLAMA_HOST'" >> ~/.bashrc
echo "export OLLAMA_PORT='$OLLAMA_PORT'" >> ~/.bashrc
echo "export OLLAMA_MODEL='$OLLAMA_MODEL'" >> ~/.bashrc

export OLLAMA_HOST OLLAMA_PORT OLLAMA_MODEL

# Testa conexão com Ollama
echo ""
echo "🔍 Testando conexão com Ollama..."
if curl -s "http://$OLLAMA_HOST:$OLLAMA_PORT/api/tags" > /dev/null 2>&1; then
    echo "✅ Ollama está acessível!"
else
    echo "⚠️  Não foi possível conectar ao Ollama em $OLLAMA_HOST:$OLLAMA_PORT"
    echo "   Verifique se o servidor está rodando."
fi

echo ""
echo "============================================"
echo "✅ Instalação concluída!"
echo "============================================"
echo ""
echo "📋 Configurações:"
echo "   OLLAMA_HOST: $OLLAMA_HOST"
echo "   OLLAMA_MODEL: $OLLAMA_MODEL"
echo "   OAuth: ${GITHUB_CLIENT_ID:+Configurado}"
echo ""
echo "🚀 Para iniciar o servidor:"
echo "   python3 github_agent_server.py"
echo ""
echo "🌐 Depois acesse: http://localhost:5000"
echo ""

# Pergunta se quer iniciar agora
read -p "Deseja iniciar o servidor agora? (s/n) [s]: " start_now

if [[ "$start_now" != "n" && "$start_now" != "N" ]]; then
    echo ""
    echo "🚀 Iniciando servidor..."
    python3 github_agent_server.py
fi
