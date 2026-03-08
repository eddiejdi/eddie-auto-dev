#!/bin/bash
# Deploy script para atualizar Grafana com as queries FASE 2

set -e

echo "🚀 Atualizar Grafana Dashboard — FASE 2"
echo "========================================"
echo ""

# Configuração padrão
GRAFANA_URL="${GRAFANA_URL:-https://grafana.rpa4all.com}"
GRAFANA_API_KEY="${GRAFANA_API_KEY:-}"

# Se não houver API key, solicitar ao usuário
if [ -z "$GRAFANA_API_KEY" ]; then
    echo "⚠️  GRAFANA_API_KEY não configurado"
    echo ""
    echo "Para obter a API key:"
    echo "  1. Acessar: $GRAFANA_URL/org/apikeys"
    echo "  2. Create API Token"
    echo "  3. Nomear como 'shared-auto-dev'"
    echo "  4. Selecionar permissão 'Edit'"
    echo "  5. Copiar o token"
    echo ""
    read -p "Cole o API token (ou pressione Enter para usar valor default): " api_key_input
    
    if [ ! -z "$api_key_input" ]; then
        GRAFANA_API_KEY="$api_key_input"
    else
        echo "❌ API key é obrigatória"
        exit 1
    fi
fi

# Exportar para o script Python
export GRAFANA_URL
export GRAFANA_API_KEY

echo ""
echo "🔧 Executando atualização..."
python3 update_grafana_dashboard_phase2.py

echo ""
echo "✅ Concluído!"
