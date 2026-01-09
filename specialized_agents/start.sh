#!/bin/bash
# Script para iniciar o Dashboard dos Agentes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Carregar variáveis de ambiente
if [ -f "$BASE_DIR/.env" ]; then
    export $(cat "$BASE_DIR/.env" | grep -v '^#' | xargs)
fi

# Ativar ambiente virtual
if [ -f "$BASE_DIR/venv/bin/activate" ]; then
    source "$BASE_DIR/venv/bin/activate"
fi

echo "🤖 Iniciando Dashboard dos Agentes Especializados..."
echo "📍 URL: http://localhost:8502"
echo ""

# Iniciar Streamlit
cd "$BASE_DIR"
streamlit run "$SCRIPT_DIR/streamlit_app.py" \
    --server.port 8502 \
    --server.address 0.0.0.0 \
    --browser.gatherUsageStats false \
    --theme.base dark
