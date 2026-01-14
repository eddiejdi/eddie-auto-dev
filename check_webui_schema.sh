#!/bin/bash
# Script para verificar schema e atualizar senha

# Copiar banco do container
docker cp open-webui:/app/backend/data/webui.db /tmp/webui.db

# Verificar tabelas
echo "=== Tabelas no banco ==="
sqlite3 /tmp/webui.db ".tables"

echo ""
echo "=== Schema da tabela user ==="
sqlite3 /tmp/webui.db "PRAGMA table_info(user);"

echo ""
echo "=== Schema da tabela auth ==="
sqlite3 /tmp/webui.db "PRAGMA table_info(auth);"

echo ""
echo "=== Dados do usuário ==="
sqlite3 /tmp/webui.db "SELECT * FROM user WHERE email='edenilson.adm@gmail.com';"

echo ""
echo "=== Dados de auth ==="
sqlite3 /tmp/webui.db "SELECT * FROM auth WHERE email='edenilson.adm@gmail.com';"
