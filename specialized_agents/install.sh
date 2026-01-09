#!/bin/bash
# Script de instalação dos Agentes Especializados

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "🤖 Instalando Agentes Programadores"
echo "=========================================="

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Por favor, instale o Python 3.11+"
    exit 1
fi

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️ Docker não encontrado. Funcionalidades de container serão limitadas."
else
    echo "✅ Docker encontrado"
fi

# Criar ambiente virtual
echo "📦 Criando ambiente virtual..."
cd "$BASE_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Instalar dependências
echo "📥 Instalando dependências..."
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

# Criar diretórios necessários
echo "📁 Criando estrutura de diretórios..."
mkdir -p "$BASE_DIR/agent_data"
mkdir -p "$BASE_DIR/backups"
mkdir -p "$BASE_DIR/dev_projects"
mkdir -p "$BASE_DIR/agent_rag"
mkdir -p "$BASE_DIR/uploads"

# Configurar variáveis de ambiente (se não existir)
ENV_FILE="$BASE_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "📝 Criando arquivo .env..."
    cat > "$ENV_FILE" << 'EOF'
# Configuração Ollama
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# GitHub Token (opcional)
GITHUB_TOKEN=

# GitHub Agent URL
GITHUB_AGENT_URL=http://localhost:8080
EOF
    echo "⚠️ Edite o arquivo .env com suas configurações"
fi

# Baixar modelos de embedding
echo "📥 Baixando modelos de embedding..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

echo ""
echo "=========================================="
echo "✅ Instalação concluída!"
echo "=========================================="
echo ""
echo "Para iniciar o dashboard:"
echo "  ./specialized_agents/start.sh"
echo ""
echo "Ou manualmente:"
echo "  source venv/bin/activate"
echo "  streamlit run specialized_agents/streamlit_app.py"
echo ""
