#!/bin/bash
# Script para atualizar senha no Open WebUI
# Tabela correta: auth (não user)

set -e

EMAIL="edenilson.teixeira@rpa4all.com"
# Prefer env var or project vault secret
NEW_PASSWORD="${WEBUI_ADMIN_PASSWORD:-}"
if [ -z "$NEW_PASSWORD" ]; then
    if command -v python3 >/dev/null 2>&1; then
        NEW_PASSWORD=$(python3 tools/vault/secret_store.py get eddie/webui_admin_password 2>/dev/null || true)
    fi
fi
if [ -z "$NEW_PASSWORD" ]; then
    echo "ERROR: admin password not provided via WEBUI_ADMIN_PASSWORD or vault item 'eddie/webui_admin_password'"
    exit 1
fi

echo "Gerando hash bcrypt para a nova senha..."
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$NEW_PASSWORD', bcrypt.gensalt()).decode())")
echo "Hash gerado"

echo ""
echo "Copiando banco de dados do container..."
docker cp open-webui:/app/backend/data/webui.db /tmp/webui.db

echo ""
echo "Atualizando senha na tabela auth..."
sqlite3 /tmp/webui.db "UPDATE auth SET password='$HASH' WHERE email='$EMAIL';"

echo ""
echo "Verificando atualização..."
sqlite3 /tmp/webui.db "SELECT email, substr(password, 1, 30) as hash_preview FROM auth WHERE email='$EMAIL';"

echo ""
echo "Copiando banco de volta para o container..."
docker cp /tmp/webui.db open-webui:/app/backend/data/webui.db

echo ""
echo "Reiniciando container..."
docker restart open-webui

echo ""
echo "========================================"
echo "Senha atualizada com sucesso!"
echo "Email: $EMAIL"
echo "(senha armazenada no cofre do projeto; não exibida)"
echo "========================================"
