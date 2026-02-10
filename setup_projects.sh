#!/bin/bash
# Script para configurar projetos no servidor

# 1. GitHub Agent README
cat > /home/homelab/projects/github-agent/README.md << 'EOFREADME'
# GitHub Agent 🤖

Agente inteligente que conecta Ollama com GitHub API via linguagem natural.

## Funcionalidades
- 💬 Chat em linguagem natural
- 📂 Listar repositórios, issues, PRs
- 🔍 Buscar repositórios
- 🔐 Autenticação via token

## Stack
- Python 3.11+ / Streamlit / Ollama / GitHub API

## Instalação
```bash
python -m venv venv && source venv/bin/activate
pip install streamlit requests
streamlit run github_agent_streamlit.py --server.port 8502
## Licença
MIT
EOFREADME

# 2. GitHub Agent .gitignore
cat > /home/homelab/projects/github-agent/.gitignore << 'EOFGIT'
venv/
__pycache__/
*.pyc
.env
*.log
.github_agent_config.json
EOFGIT

# 3. RAG Dashboard README
cat > /home/homelab/projects/rag-dashboard/README.md << 'EOFREADME'
# RAG Dashboard 📊

Dashboard Streamlit para monitorar e gerenciar o sistema RAG (Retrieval Augmented Generation).

## Funcionalidades
- 📈 Monitoramento de coleções
- 📄 Visualização de documentos indexados
- 🔍 Busca semântica
- 📊 Estatísticas do sistema

## Stack
- Python / Streamlit / ChromaDB

## Uso
```bash
streamlit run rag_dashboard.py --server.port 8501
## Licença
MIT
EOFREADME

cat > /home/homelab/projects/rag-dashboard/.gitignore << 'EOFGIT'
venv/
__pycache__/
*.pyc
.env
*.log
EOFGIT

# 4. Homelab Scripts README
cat > /home/homelab/projects/homelab-scripts/README.md << 'EOFREADME'
# Homelab Scripts 🏠

Scripts de automação e treinamento para o homelab.

## Scripts
- `smart_train.sh` - Treinamento inteligente (roda quando sistema idle)
- `quick_train.sh` - Treinamento rápido
- `train_python_docs.sh` - Treina com documentação Python
- `check_status.sh` - Verifica status dos serviços
- `server-agent.py` - Agente de monitoramento
- `bitcoin_knowledge.py` - Base de conhecimento Bitcoin

## Systemd
- `python-training.service` - Serviço de treinamento
- `python-training.timer` - Timer para treinamento automático

## Licença
MIT
EOFREADME

cat > /home/homelab/projects/homelab-scripts/.gitignore << 'EOFGIT'
*.log
.env
__pycache__/
EOFGIT

# 5. GitHub MCP Server - já tem README, só .gitignore
cat > /home/homelab/projects/github-mcp-server/.gitignore << 'EOFGIT'
venv/
node_modules/
__pycache__/
*.pyc
.env
*.log
dist/
EOFGIT

echo "✅ Arquivos criados com sucesso!"
