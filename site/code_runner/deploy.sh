#!/bin/bash
# Deploy do Code Runner para o homelab
# Uso: ./deploy.sh

set -e

REMOTE="homelab@192.168.15.2"
CONTAINER_NAME="code-runner"
IMAGE_NAME="rpa4all/code-runner"
PORT="2000"

echo "🚀 Deploy RPA4ALL Code Runner"
echo "=============================="

# Para e remove container existente
echo "📦 Parando container existente..."
ssh $REMOTE "docker stop $CONTAINER_NAME 2>/dev/null || true"
ssh $REMOTE "docker rm $CONTAINER_NAME 2>/dev/null || true"

# Copia arquivos para o homelab
echo "📤 Copiando arquivos..."
scp -r $(dirname "$0")/* $REMOTE:/tmp/code-runner/

# Build da imagem
echo "🔨 Building imagem Docker..."
ssh $REMOTE "cd /tmp/code-runner && docker build -t $IMAGE_NAME ."

# Inicia container
echo "▶️ Iniciando container..."
ssh $REMOTE "docker run -d \
    --name $CONTAINER_NAME \
    --restart=always \
    -p $PORT:5000 \
    -e MAX_EXECUTION_TIME=30 \
    -e MAX_MEMORY_MB=256 \
    -e MAX_OUTPUT_SIZE=65536 \
    $IMAGE_NAME"

# Verifica status
echo "✅ Verificando status..."
sleep 3
ssh $REMOTE "docker logs $CONTAINER_NAME --tail 10"

echo ""
echo "=============================="
echo "✅ Deploy concluído!"
echo "🌐 API: http://192.168.15.2:$PORT"
echo "📖 Docs: http://192.168.15.2:$PORT/api/v2/runtimes"
echo ""
echo "Teste:"
echo "curl -X POST http://192.168.15.2:$PORT/api/v2/execute \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"language\":\"python\",\"files\":[{\"content\":\"print(\\\"Hello RPA4ALL!\\\")\"}]}'"
