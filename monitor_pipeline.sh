#!/bin/bash
# Script para acompanhar pipeline do GitHub Actions
# Uso: ./monitor_pipeline.sh

REPO="eddiejdi/eddie-auto-dev"
BRANCH="main"

echo "🔍 Acompanhando Pipeline do GitHub Actions"
echo "📍 Repositório: $REPO"
echo "📌 Branch: $BRANCH"
echo

# Tentar com gh CLI primeiro
if command -v gh &> /dev/null; then
    echo "📊 Status dos Workflows (últimos 10):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    gh run list --limit 10 | while read -r status conclusion message workflow branch trigger run_id duration timestamp; do
        # Colorir status
        case "$status" in
            "in_progress") 
                STATUS_ICON="⏳"
                ;;
            "completed")
                if [ "$conclusion" == "success" ]; then
                    STATUS_ICON="✅"
                else
                    STATUS_ICON="❌"
                fi
                ;;
            "queued")
                STATUS_ICON="⏸️ "
                ;;
            *)
                STATUS_ICON="❓"
                ;;
        esac
        
        printf "%s %-40s %-30s %s\n" "$STATUS_ICON" "$message" "$workflow" "$duration"
    done | head -12
    
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "📈 Resumo:"
    echo "  ✅ = Sucesso"
    echo "  ❌ = Falha"
    echo "  ⏳ = Em progresso"
    echo "  ⏸️  = Na fila"
    echo
    echo "🔗 Dashboard completo:"
    echo "  https://github.com/$REPO/actions"
    
else
    echo "❌ GitHub CLI (gh) não instalado"
    echo
    echo "Para instalar:"
    echo "  Ubuntu/Debian: sudo apt-get install gh"
    echo "  macOS: brew install gh"
    echo "  Outros: https://github.com/cli/cli"
    echo
    echo "Depois faça login:"
    echo "  gh auth login"
    echo
    echo "Para ver o status agora, acesse:"
    echo "  🌐 https://github.com/$REPO/actions"
fi
