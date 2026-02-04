#!/bin/bash
# Script para armazenar credenciais do PostgreSQL no Bitwarden
# Execute após fazer login: bw login

set -e

echo "==========================================="
echo "ARMAZENANDO CREDENCIAIS NO BITWARDEN"
echo "==========================================="

# Verifica se está logado
if ! bw login --check &>/dev/null; then
    echo "❌ Você precisa fazer login primeiro:"
    echo "   bw login"
    exit 1
fi

# Desbloqueia o vault (se necessário)
export BW_SESSION=$(bw unlock --raw)

# Cria o item no formato JSON
ITEM_JSON=$(cat <<'EOF'
{
  "organizationId": null,
  "folderId": null,
  "type": 1,
  "name": "Eddie PostgreSQL - Agent Memory (Homelab)",
  "notes": "Credenciais do PostgreSQL para sistema de memória dos agentes especializados.\nContainer: eddie-postgres\nConfigurado em: 2026-02-04",
  "favorite": false,
  "fields": [
    {
      "name": "Container",
      "value": "eddie-postgres",
      "type": 0
    },
    {
      "name": "Port",
      "value": "5432",
      "type": 0
    },
    {
      "name": "Connection String",
      "value": "postgresql://postgres:eddie_memory_2026@192.168.15.2:5432/postgres",
      "type": 1
    }
  ],
  "login": {
    "uris": [
      {
        "match": null,
        "uri": "postgresql://192.168.15.2:5432"
      }
    ],
    "username": "postgres",
    "password": "eddie_memory_2026",
    "totp": null
  }
}
EOF
)

# Adiciona o item
echo "📝 Criando item no Bitwarden..."
ITEM_ID=$(echo "$ITEM_JSON" | bw encode | bw create item | jq -r '.id')

if [ -n "$ITEM_ID" ]; then
    echo "✅ Credenciais armazenadas com sucesso!"
    echo "   Item ID: $ITEM_ID"
    echo "   Nome: Eddie PostgreSQL - Agent Memory (Homelab)"
    
    # Sincroniza
    bw sync
    echo "✅ Sincronização concluída"
else
    echo "❌ Erro ao criar item"
    exit 1
fi

# Limpa sessão
unset BW_SESSION

echo ""
echo "==========================================="
echo "✅ CREDENCIAIS SEGURAS NO BITWARDEN"
echo "==========================================="
echo ""
echo "Para recuperar a senha:"
echo "  bw get password 'Eddie PostgreSQL - Agent Memory (Homelab)'"
echo ""
echo "Para recuperar o connection string:"
echo "  bw get item 'Eddie PostgreSQL - Agent Memory (Homelab)' | jq -r '.fields[] | select(.name==\"Connection String\") | .value'"
