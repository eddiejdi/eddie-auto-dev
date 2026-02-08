#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
VENV_DIR="${ROOT_DIR}/.venv"
REQ_FILE="${ROOT_DIR}/specialized_agents/requirements.txt"

echo "🔧 Configurando ambiente do projeto"

if [[ -f "$ENV_FILE" ]]; then
  echo "✅ .env já existe em ${ENV_FILE} (não será sobrescrito)"
else
  echo "📝 Criando .env em ${ENV_FILE}"
# create .env with updated DB
  cat > "$ENV_FILE" << 'EOF'
# Eddie Auto-Dev
OLLAMA_HOST=http://192.168.15.2:11434
CODE_RUNNER_URL=http://192.168.15.2:2000
SPECIALIZED_AGENTS_API=http://192.168.15.2:8503
DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres
EOF
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "🐍 Criando virtualenv em ${VENV_DIR}"
  python3 -m venv "$VENV_DIR"
fi

echo "📦 Instalando dependências"
"${VENV_DIR}/bin/pip" install --upgrade pip

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/pip" install -r "$REQ_FILE"
  echo "✅ Requirements instalados: ${REQ_FILE}"
else
  echo "⚠️ Arquivo requirements não encontrado: ${REQ_FILE}"
fi

echo "✅ Ambiente configurado"