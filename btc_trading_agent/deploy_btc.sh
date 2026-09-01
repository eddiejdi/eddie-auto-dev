#!/bin/bash
# deploy_btc_v5.sh — wrapper local para o deploy profile-aware atual
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== BTC Trading Optimizer v5 — Profile Deploy ==="
echo "Este fluxo agora usa os profiles BTC atuais e valida secrets antes do restart."
echo ""

bash "${REPO_ROOT}/scripts/deploy_btc_trading_profiles.sh"
