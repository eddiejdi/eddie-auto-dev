#!/bin/bash
set -e

echo "=== Open WebUI — Downgrade para Versão Estável ==="
echo "Versão anterior: main (instável)"
echo "Versão alvo: v0.3.5 (estável)"
echo ""

# Backup antes de qualquer coisa
echo "1️⃣ Criando backup..."
BACKUP_DATE=$(date +%s)
docker run --rm \
  -v open-webui:/data \
  alpine tar czf /tmp/open-webui-backup-${BACKUP_DATE}.tar.gz /data 2>/dev/null
echo "✅ Backup criado: /tmp/open-webui-backup-${BACKUP_DATE}.tar.gz"

# Parar container
echo ""
echo "2️⃣ Parando container..."
docker stop open-webui || true
sleep 2
echo "✅ Container parado"

# Remover container (volume persiste)
echo ""
echo "3️⃣ Removendo container..."
docker rm open-webui || true
echo "✅ Container removido"

# Pull nova imagem
echo ""
echo "4️⃣ Download da versão estável v0.3.5..."
docker pull ghcr.io/open-webui/open-webui:v0.3.5
echo "✅ Imagem v0.3.5 baixada"

# Iniciar com versão nova
echo ""
echo "5️⃣ Iniciando container com v0.3.5..."
docker run -d \
  --name open-webui \
  --restart always \
  -p 3000:8080 \
  -e ANONYMIZED_TELEMETRY=false \
  -e ENV=prod \
  -e ENABLE_OAUTH_SIGNUP=true \
  -e OAUTH_PROVIDER_NAME=Authentik \
  -e OPENID_PROVIDER_URL=https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration \
  -e OAUTH_CLIENT_ID=authentik-openwebui \
  -e OAUTH_CLIENT_SECRET=openwebui-sso-secret-2026 \
  -e OAUTH_SCOPES="openid email profile" \
  -e DO_NOT_TRACK=true \
  -e SCARF_NO_ANALYTICS=true \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e USE_OLLAMA_DOCKER=false \
  -e USE_CUDA_DOCKER=false \
  -e USE_SLIM_DOCKER=false \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:v0.3.5

echo "✅ Container iniciado com v0.3.5"

# Aguardar inicialização
echo ""
echo "6️⃣ Aguardando inicialização completa (30s)..."
sleep 30

# Verificar logs
echo ""
echo "7️⃣ Verificando logs (últimas 30 linhas)..."
docker logs open-webui --tail 30

# Verificar se container está saudável
echo ""
echo "8️⃣ Verificando status..."
HEALTH=$(docker inspect open-webui --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
echo "Status do container: $HEALTH"

if [ "$HEALTH" = "running" ]; then
  echo ""
  echo "✅ DOWNGRADE COMPLETO COM SUCESSO!"
  echo ""
  echo "Próximas ações:"
  echo "1. Aguarde 2 minutos para database migrations"
  echo "2. Acesse: https://openwebui.rpa4all.com"
  echo "3. Clique em 'Sign in with Authentik'"
  echo "4. Verifique se o erro 'unsupported_algorithm' foi resolvido"
  echo ""
  echo "Se tiver problema:"
  echo "  docker logs open-webui -f  # Acompanhar logs em tempo real"
  echo "  curl http://127.0.0.1:3000/api/config  # Testar API"
  echo ""
else
  echo "❌ AVISO: Container não está em estado 'running'"
  echo "Verifique os logs acima"
fi
