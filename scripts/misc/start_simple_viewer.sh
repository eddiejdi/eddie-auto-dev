#!/bin/bash

# Script para iniciar a interface simples de conversas
# ==================================================

cd ~/myClaude

# Ativar virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment ativado (bin/activate)"
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
    echo "✅ Virtual environment ativado (Scripts/activate)"
fi

echo ""
echo "🚀 Iniciando Interface Simples de Conversas"
echo "==========================================="
echo ""
echo "✅ A interface estará disponível em:"
echo "   https://heights-treasure-auto-phones.trycloudflare.com"
echo ""
echo "🎯 Pressione Ctrl+C para parar"
echo ""

# Iniciar streamlit com a interface simples usando python -m
python -m streamlit run specialized_agents/simple_conversation_viewer.py --logger.level=error
