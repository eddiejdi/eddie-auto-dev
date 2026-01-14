#!/bin/bash
# Script para atualizar senha no Open WebUI
# Tabela correta: auth (não user)

set -e

EMAIL="edenilson.adm@gmail.com"
NEW_PASSWORD="Eddie@2026"

echo "Gerando hash bcrypt para a nova senha..."
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$NEW_PASSWORD', bcrypt.gensalt()).decode())")
echo "Hash gerado: $HASH"

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
echo "Senha: $NEW_PASSWORD"
echo "========================================"
