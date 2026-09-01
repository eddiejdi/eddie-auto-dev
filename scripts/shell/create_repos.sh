#!/bin/bash
# Script para criar repos no GitHub e fazer push

set -e

create_and_push() {
    local path=$1
    local name=$2
    local desc=$3
    
    echo ""
    echo "=== $name ==="
    cd "$path"
    
    # Verifica se repo já existe
    if gh repo view "eddiejdi/$name" &>/dev/null; then
        echo "Repo já existe, atualizando..."
        git remote remove origin 2>/dev/null || true
        git remote add origin "https://github.com/eddiejdi/$name.git"
    else
        echo "Criando novo repo..."
        gh repo create "$name" --public --description "$desc" --source=. --remote=origin
    fi
    
    # Push
    git push -u origin main --force
    echo "✅ $name - Push realizado!"
}

# Criar repos
create_and_push "/home/homelab/projects/github-agent" "github-agent" "Agente inteligente Ollama + GitHub API"
create_and_push "/home/homelab/projects/github-mcp-server" "github-mcp-server" "MCP Server para GitHub com 35+ tools"
create_and_push "/home/homelab/projects/homelab-scripts" "homelab-scripts" "Scripts de automação para homelab"
create_and_push "/home/homelab/projects/rag-dashboard" "rag-dashboard" "Dashboard Streamlit para RAG"

echo ""
echo "🎉 Todos os repositórios criados e atualizados!"
echo ""
echo "URLs:"
echo "- https://github.com/eddiejdi/github-agent"
echo "- https://github.com/eddiejdi/github-mcp-server"
echo "- https://github.com/eddiejdi/homelab-scripts"
echo "- https://github.com/eddiejdi/rag-dashboard"
