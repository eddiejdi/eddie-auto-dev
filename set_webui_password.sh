#!/bin/bash
# Script para definir senha no Open WebUI

# Gerar hash bcrypt
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'Eddie@2026', bcrypt.gensalt()).decode())")

echo "Hash gerado: $HASH"

# Copiar banco de dados do container
docker cp open-webui:/app/backend/data/webui.db /tmp/webui.db

# Atualizar senha no banco
sqlite3 /tmp/webui.db "UPDATE user SET password='$HASH' WHERE email='edenilson.adm@gmail.com';"

# Verificar
echo "Verificando atualização:"
sqlite3 /tmp/webui.db "SELECT email, substr(password, 1, 30) FROM user WHERE email='edenilson.adm@gmail.com';"

# Copiar de volta
docker cp /tmp/webui.db open-webui:/app/backend/data/webui.db

# Reiniciar container
docker restart open-webui

echo "Senha atualizada para: Eddie@2026"
