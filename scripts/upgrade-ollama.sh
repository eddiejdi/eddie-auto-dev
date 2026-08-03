#!/bin/bash
set -euo pipefail

# Upgrade Ollama 0.17.6 → 0.32.5 (ou mais recente)
# Objetivo: destravar suporte a LFM2.5-VL-450M (tensor 'output_norm' faltando em 0.17.6)
# Risco: Vulkan ativado por padrão em 0.32.5 pode interferir com GPUs de produção

echo "📦 Download e upgrade do Ollama..."

VERSION="0.32.5"
ARCH="amd64"
URL="https://ollama.com/download/ollama-linux-${ARCH}"
TMP_DIR="/tmp/ollama-upgrade"
BACKUP_DIR="/usr/local/bin/ollama.backup.$(date +%Y%m%d)"

# 1. Download
echo "→ Download da versão ${VERSION}..."
mkdir -p "$TMP_DIR"
curl -L -o "${TMP_DIR}/ollama" "$URL"
chmod +x "${TMP_DIR}/ollama"

# 2. Verifica versão baixada
DOWNLOADED_VERSION=$("${TMP_DIR}/ollama" --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || echo "desconhecida")
echo "   Versão baixada: ${DOWNLOADED_VERSION}"

# 3. Backup da versão atual
CURRENT_VERSION=$(/usr/local/bin/ollama --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || echo "desconhecida")
echo "   Versão atual: ${CURRENT_VERSION}"
echo "→ Criando backup..."
sudo cp /usr/local/bin/ollama "$BACKUP_DIR"
sudo chown root:root "$BACKUP_DIR"

# 4. Instala nova versão (não reinicia serviço ainda)
echo "→ Instalando nova versão..."
sudo cp "${TMP_DIR}/ollama" /usr/local/bin/ollama
sudo chmod 755 /usr/local/bin/ollama

# 5. Reinicia serviço
echo "→ Reiniciando serviço Ollama..."
sudo systemctl restart ollama

# 6. Aguarda startup
echo "→ Aguardando Ollama iniciar..."
sleep 10

# 7. Verifica saúde
if curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
    echo "✅ Ollama rodando após upgrade"
    NEW_VERSION=$(curl -s http://127.0.0.1:11434/version 2>/dev/null || /usr/local/bin/ollama --version)
    echo "   Nova versão: ${NEW_VERSION}"
else
    echo "❌ Ollama não respondeu após upgrade — revertendo..."
    sudo cp "$BACKUP_DIR" /usr/local/bin/ollama
    sudo systemctl restart ollama
    exit 1
fi

# 8. Testa LFM2.5-VL-450M (opcional, requer modelo baixado)
echo ""
echo "📋 Para testar VL-450M:"
echo "   ollama pull lm2.5-vl:450m"
echo "   ollama run lm2.5-vl:450m 'descreva esta imagem' <imagem.jpg>"
echo ""
echo "⚠️  Atenção: Vulkan ativado por padrão. Se houver conflitos com NVIDIA:"
echo "   Exportar OLLAMA_VULKAN=0 no service file ou /etc/default/ollama"

# Cleanup
rm -rf "$TMP_DIR"
echo ""
echo "✅ Upgrade concluído!"
