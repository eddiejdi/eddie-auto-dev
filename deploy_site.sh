#!/bin/bash
# Deploy script para sincronizar arquivos do site para www.rpa4all.com
# Uso: ./deploy_site.sh

set -euo pipefail

SITE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/site" && pwd )"
REMOTE_USER="homelab"
REMOTE_HOST="192.168.15.2"
REMOTE_PATH="/var/www/rpa4all.com"

echo "🚀 Deploy do Site RPA4ALL"
echo "=========================="
echo "Local: $SITE_DIR"
echo "Remoto: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
echo ""

# Arquivos a deployar
FILES=(
  "index.html"
  "ide.js"
  "styles.css"
  "script.js"
  "openwebui-config.json"
)

echo "📦 Copiando arquivos..."
for file in "${FILES[@]}"; do
  if [ -f "$SITE_DIR/$file" ]; then
    echo "  → $file"
    scp "$SITE_DIR/$file" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/$file" || {
      echo "❌ Erro ao copiar $file"
      exit 1
    }
  else
    echo "  ⚠️  $file não encontrado (skipped)"
  fi
done

echo ""
echo "✅ Deploy concluído!"
echo "Verifique: https://www.rpa4all.com"
