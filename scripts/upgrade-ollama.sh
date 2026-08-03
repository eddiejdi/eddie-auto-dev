#!/bin/bash
set -euo pipefail

# Upgrade Ollama 0.17.6 → versão estável mais recente
# Objetivo: destravar suporte a LFM2.5-VL-450M (tensor 'output_norm' faltando em 0.17.6)
#
# Histórico:
# - Incidente 2026-08-02: binário canário incompleto (sem llama-server)
# - Sucesso 2026-08-03: tarball oficial do GitHub, layout bin+lib validado, deploy em 2 etapas (GPU1 → GPU0)
#
# Desde ~v0.31, o Ollama usa layout de biblioteca dividida:
#   bin/ollama (dinamicamente ligado) + lib/ollama/*.so (CUDA/Vulkan/CPU backends)
# Substituir só o binário sem sincronizar lib/ollama quebra o serviço.

VERSION_TAG="${1:-v0.32.5}"
URL="https://github.com/ollama/ollama/releases/download/${VERSION_TAG}/ollama-linux-amd64.tar.zst"
TMP_DIR="/tmp/ollama-upgrade-$$"
TS="$(date +%Y%m%d_%H%M%S)"
BIN_BACKUP="/usr/local/bin/ollama.backup.pre_${VERSION_TAG//./}_${TS}"
LIB_BACKUP="/usr/local/lib/ollama.backup.pre_${VERSION_TAG//./}_${TS}"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

echo "📦 Upgrade Ollama → ${VERSION_TAG}"

# 1. Download tarball oficial (.tar.zst)
echo "→ Download da release oficial..."
mkdir -p "$TMP_DIR"
if ! curl -fL --connect-timeout 30 --max-time 900 --retry 3 -o "${TMP_DIR}/ollama.tar.zst" "$URL"; then
    echo "❌ Download falhou"
    exit 1
fi

FILE_SIZE=$(stat -c%s "${TMP_DIR}/ollama.tar.zst" 2>/dev/null || echo 0)
if [[ $FILE_SIZE -lt 500000000 ]]; then
    echo "❌ Arquivo baixado muito pequeno (${FILE_SIZE} bytes) — provavelmente página de erro ou URL assinada expirada (validade ~1h)"
    head -c 500 "${TMP_DIR}/ollama.tar.zst"
    exit 1
fi
echo "   Tamanho: $((FILE_SIZE / 1024 / 1024))MB ✅"

# 2. Extrai (produz ./bin/ollama e ./lib/ollama/*)
echo "→ Extraindo..."
tar --use-compress-program=unzstd -xf "${TMP_DIR}/ollama.tar.zst" -C "$TMP_DIR"

if [[ ! -f "${TMP_DIR}/bin/ollama" ]]; then
    echo "❌ bin/ollama não encontrado no tarball"
    exit 1
fi
if [[ ! -f "${TMP_DIR}/lib/ollama/llama-server" ]]; then
    echo "❌ lib/ollama/llama-server ausente — binário incompleto (mesmo problema do incidente 2026-08-02)"
    exit 1
fi
if ! file "${TMP_DIR}/bin/ollama" | grep -q "ELF"; then
    echo "❌ bin/ollama não é um executável válido"
    exit 1
fi
chmod +x "${TMP_DIR}/bin/ollama"

DOWNLOADED_VERSION=$("${TMP_DIR}/bin/ollama" --version 2>&1 | grep -oP 'client version is \K[\d.]+' || echo "desconhecida")
echo "   Versão baixada: ${DOWNLOADED_VERSION}"

# 3. Backup binário + lib atuais
echo "→ Backup: ${BIN_BACKUP}, ${LIB_BACKUP}"
sudo cp -a /usr/local/bin/ollama "$BIN_BACKUP"
sudo cp -a /usr/local/lib/ollama "$LIB_BACKUP"

rollback() {
    echo "⚠️  Revertendo para backup..."
    sudo cp "$BIN_BACKUP" /usr/local/bin/ollama
    sudo rsync -a --delete "${LIB_BACKUP}/" /usr/local/lib/ollama/
    sudo systemctl restart ollama-gpu1 2>/dev/null || true
    sudo systemctl restart ollama 2>/dev/null || true
    echo "Rollback concluído."
}

# 4. Troca binário (via mv atômico — evita 'Text file busy' com serviço rodando) + lib
echo "→ Substituindo binário e libs..."
sudo cp "${TMP_DIR}/bin/ollama" /usr/local/bin/ollama.new
sudo chmod 755 /usr/local/bin/ollama.new
sudo chown root:root /usr/local/bin/ollama.new
sudo mv /usr/local/bin/ollama.new /usr/local/bin/ollama
sudo rsync -a --delete "${TMP_DIR}/lib/ollama/" /usr/local/lib/ollama/
sudo chown -R root:root /usr/local/lib/ollama

# 5. GPU1 primeiro (não-crítico) — depois GPU0 (trading, por último e com cautela)
for svc in ollama-gpu1 ollama; do
    echo "→ Reiniciando ${svc}..."
    sudo systemctl restart "$svc"
    sleep 10

    port=11434
    [[ "$svc" == "ollama-gpu1" ]] && port=11435

    ok=""
    for i in $(seq 1 12); do
        if curl -sf --max-time 3 "http://127.0.0.1:${port}/api/version" > /dev/null; then
            ok=1
            break
        fi
        sleep 5
    done

    if [[ -z "$ok" ]]; then
        echo "❌ ${svc} não respondeu em ${port} após restart"
        rollback
        exit 1
    fi
    echo "✅ ${svc} respondendo em ${port} ($(curl -s http://127.0.0.1:${port}/api/version))"
done

echo ""
echo "📊 Resumo: ${DOWNLOADED_VERSION} instalado em ambos os serviços GPU0/GPU1"
echo "   Backup binário: ${BIN_BACKUP}"
echo "   Backup libs:    ${LIB_BACKUP}"
echo ""
echo "⚠️  Rollback manual se necessário:"
echo "   sudo cp ${BIN_BACKUP} /usr/local/bin/ollama"
echo "   sudo rsync -a --delete ${LIB_BACKUP}/ /usr/local/lib/ollama/"
echo "   sudo systemctl restart ollama-gpu1 ollama"
echo ""
echo "✅ Upgrade concluído!"
