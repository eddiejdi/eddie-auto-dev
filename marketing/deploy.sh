#!/usr/bin/env bash
# ============================================================
# Deploy do módulo Marketing RPA4ALL
# Executa migração do banco, copia systemd units, e ativa serviços
#
# Uso:
#   bash marketing/deploy.sh              # Deploy completo
#   bash marketing/deploy.sh --dry-run    # Apenas mostra o que faria
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "🔍 DRY RUN — nada será alterado"
fi

run_cmd() {
    if $DRY_RUN; then
        echo "  [dry-run] $*"
    else
        echo "  → $*"
        eval "$@"
    fi
}

echo "═══════════════════════════════════════════════"
echo "  Deploy Marketing RPA4ALL"
echo "═══════════════════════════════════════════════"

# 1. Migração do banco
echo ""
echo "📦 1/5 — Migração do banco de dados"
if $DRY_RUN; then
    run_cmd "python3 $SCRIPT_DIR/db_migrate.py --dry-run"
else
    run_cmd "python3 $SCRIPT_DIR/db_migrate.py"
fi

# 2. Copiar systemd units
echo ""
echo "⚙️  2/5 — Instalação dos serviços systemd"
UNITS=(
    marketing-api.service
    marketing-daily-report.service
    marketing-daily-report.timer
    marketing-email-drip.service
    marketing-email-drip.timer
    marketing-x-posts.service
    marketing-x-posts.timer
)
for unit in "${UNITS[@]}"; do
    run_cmd "sudo cp $PROJECT_DIR/systemd/$unit /etc/systemd/system/$unit"
done
run_cmd "sudo systemctl daemon-reload"

# 3. Ativar timers e serviço API
echo ""
echo "🚀 3/5 — Ativação dos serviços"
run_cmd "sudo systemctl enable --now marketing-api.service"
run_cmd "sudo systemctl enable --now marketing-daily-report.timer"
run_cmd "sudo systemctl enable --now marketing-email-drip.timer"
run_cmd "sudo systemctl enable --now marketing-x-posts.timer"

# 4. Nginx snippet
echo ""
echo "🌐 4/5 — Configuração nginx"
run_cmd "sudo cp $PROJECT_DIR/config/marketing-nginx.conf /etc/nginx/snippets/marketing.conf"
echo "  ⚠️  MANUAL: Adicionar 'include snippets/marketing.conf;' no server block de rpa4all.com"
echo "  ⚠️  Depois: sudo nginx -t && sudo systemctl reload nginx"

# 5. Verificação
echo ""
echo "✅ 5/5 — Verificação"
if ! $DRY_RUN; then
    echo "  Aguardando API iniciar..."
    sleep 3
    if curl -sf http://localhost:8520/marketing/health > /dev/null 2>&1; then
        echo "  ✅ Marketing API respondendo em :8520"
    else
        echo "  ⚠️  Marketing API ainda não respondeu — verificar logs:"
        echo "     journalctl -u marketing-api.service -n 20"
    fi

    echo ""
    echo "  Timers ativos:"
    systemctl list-timers marketing-* --no-pager 2>/dev/null || true
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Deploy concluído!"
echo ""
echo "  📋 Próximos passos manuais:"
echo "  1. Configurar nginx (include snippets/marketing.conf)"
echo "  2. Configurar Meta Pixel ID na landing page"
echo "  3. Configurar Google Tag Manager ID na landing page"
echo "  4. Aprovar budget de campanhas (🔒 APPROVE)"
echo "═══════════════════════════════════════════════"
