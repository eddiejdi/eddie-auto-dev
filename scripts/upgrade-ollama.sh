#!/bin/bash
set -euo pipefail

# Upgrade Ollama 0.17.6 → latest stable
# Objetivo: destravar suporte a LFM2.5-VL-450M (tensor 'output_norm' faltando em 0.17.6)
# Incidente 2026-08-02: binário canary incompleto (sem llama-server)
# Solução: usar tarball oficial do GitHub releases + validar binários

echo "📦 Download e upgrade do Ollama..."

# Usa latest stable do GitHub (não canary!)
# Asset correto: ollama-linux-amd64.tar.zst (inclui llama-server + CUDA)
VERSION_TAG="v0.32.5"
URL="https://github.com/ollama/ollama/releases/download/${VERSION_TAG}/ollama-linux-amd64.tar.zst"
TMP_DIR="/tmp/ollama-upgrade-$$"
BACKUP_DIR="/usr/local/bin/ollama.backup.$(date +%Y%m%d_%H%M%S)"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# 1. Download tarball oficial (.zst = zstd compressed)
echo "→ Download da release oficial (${VERSION_TAG})..."
mkdir -p "$TMP_DIR"

# Usa curl com retry e timeout maior (download ~1.3GB pode demorar)
if ! curl -L --connect-timeout 30 --max-time 3600 -o "${TMP_DIR}/ollama.tar.zst" "$URL"; then
    echo "❌ Download falhou após timeout"
    exit 1
fi

# Verifica tamanho mínimo (deve ser >100MB para incluir todos os binários)
FILE_SIZE=$(stat -c%s "${TMP_DIR}/ollama.tar.zst" 2>/dev/null || echo 0)
if [[ $FILE_SIZE -lt 100000000 ]]; then
    echo "❌ Arquivo baixado muito pequeno (${FILE_SIZE} bytes) — provavelmente página de erro"
    cat "${TMP_DIR}/ollama.tar.zst" | head -3
    exit 1
fi
echo "   Tamanho: $(echo "scale=2; $FILE_SIZE/1024/1024" | bc)MB ✅"

# 2. Extrai (.zst = zstd)
echo "→ Extraindo (zstd)..."
if ! command -v unzstd &>/dev/null && ! command -v zstd &>/dev/null; then
    echo "⚠️  zstd não encontrado, tentando com tar --use-compress-program..."
    tar --use-compress-program=zstd -xf "${TMP_DIR}/ollama.tar.zst" -C "$TMP_DIR"
else
    unzstd -dk -o "${TMP_DIR}/ollama.tar" "${TMP_DIR}/ollama.tar.zst" 2>/dev/null || \
    zstd -d -k -o "${TMP_DIR}/ollama.tar" "${TMP_DIR}/ollama.tar.zst"
    tar -xf "${TMP_DIR}/ollama.tar" -C "$TMP_DIR"
    rm "${TMP_DIR}/ollama.tar"
fi

# 3. Valida presença de binários críticos
echo "→ Validando integridade dos binários..."
if [[ ! -f "${TMP_DIR}/ollama" ]]; then
    echo "❌ Binário 'ollama' não encontrado no tarball"
    exit 1
fi

# Verifica se é ELF válido (não HTML/error page)
if ! file "${TMP_DIR}/ollama" | grep -q "ELF"; then
    echo "❌ Binário não é um executável válido (é uma página de erro?)"
    cat "${TMP_DIR}/ollama" | head -5
    exit 1
fi

chmod +x "${TMP_DIR}/ollama"

# 4. Verifica versão baixada
DOWNLOADED_VERSION=$("${TMP_DIR}/ollama" --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || echo "desconhecida")
echo "   Versão baixada: ${DOWNLOADED_VERSION}"

# 5. Backup da versão atual
CURRENT_VERSION=$(/usr/local/bin/ollama --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || echo "desconhecida")
echo "   Versão atual: ${CURRENT_VERSION}"
echo "→ Criando backup..."
sudo cp /usr/local/bin/ollama "$BACKUP_DIR"
sudo chown root:root "$BACKUP_DIR"

# 6. Para serviço e substitui binário
echo "→ Parando Ollama..."
sudo pkill -9 ollama || true
sleep 2

echo "→ Substituindo binário..."
sudo cp "${TMP_DIR}/ollama" /usr/local/bin/ollama
sudo chmod 755 /usr/local/bin/ollama

# 7. Inicia serviço
echo "→ Iniciando Ollama..."
sudo systemctl start ollama
sleep 8

# 8. Verifica saúde
echo "→ Verificando saúde..."
if curl -s --max-time 10 http://127.0.0.1:11434/api/tags > /dev/null; then
    echo "✅ Ollama respondendo"
else
    echo "❌ Ollama não respondeu — revertendo..."
    sudo pkill -9 ollama || true
    sudo cp "$BACKUP_DIR" /usr/local/bin/ollama
    sudo systemctl start ollama
    exit 1
fi

# 9. Testa geração real (não só API tags)
echo "→ Testando geração com modelo existente..."
TEST_OUTPUT=$(timeout 60 curl -s -X POST http://127.0.0.1:11434/api/generate \
    -H "Content-Type: application/json" \
    -d '{"model":"gemma3:1b","prompt":"test","stream":false}' 2>&1)

if echo "$TEST_OUTPUT" | grep -q '"done":true'; then
    echo "✅ Geração funcionando"
else
    echo "⚠️  Geração falhou (pode ser problema de modelo, não do binário):"
    echo "$TEST_OUTPUT" | head -c 200
fi

echo ""
echo "📊 Resumo:"
echo "   Versão anterior: ${CURRENT_VERSION}"
echo "   Versão instalada: ${DOWNLOADED_VERSION}"
echo "   Backup: ${BACKUP_DIR}"
echo ""
echo "📋 Para testar LFM2.5-VL-450M:"
echo "   ollama run hf.co/LiquidAI/LFM2.5-VL-450M-GGUF:Q4_K_M:gpu1 'descreva esta imagem' <img.jpg"
echo ""
echo "⚠️  Se houver problemas, rollback manual:"
echo "   sudo cp ${BACKUP_DIR} /usr/local/bin/ollama && sudo systemctl restart ollama"
echo ""
echo "✅ Upgrade concluído!"
