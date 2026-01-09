#!/bin/bash
# Script para inicializar git e fazer push

GITHUB_USER="eddieoz"  # Ajuste se necessário

# Função para setup de um projeto
setup_git() {
    local project_path=$1
    local repo_name=$2
    
    echo "=== Configurando $repo_name ==="
    cd "$project_path" || exit 1
    
    # Inicializa git se não existir
    if [ ! -d ".git" ]; then
        git init
        git branch -M main
    fi
    
    # Configura usuário
    git config user.email "eddieoz@gmail.com"
    git config user.name "Eddie Oz"
    
    # Add e commit
    git add -A
    git commit -m "Initial commit - project setup" 2>/dev/null || echo "Nada para commit"
    
    echo "✅ $repo_name configurado"
}

# Setup cada projeto
setup_git "/home/homelab/projects/github-agent" "github-agent"
setup_git "/home/homelab/projects/github-mcp-server" "github-mcp-server"
setup_git "/home/homelab/projects/homelab-scripts" "homelab-scripts"
setup_git "/home/homelab/projects/rag-dashboard" "rag-dashboard"

echo ""
echo "✅ Todos os projetos configurados com git!"
echo ""
echo "Para criar repos no GitHub e fazer push, execute:"
echo "gh repo create <nome> --public --source=. --push"
