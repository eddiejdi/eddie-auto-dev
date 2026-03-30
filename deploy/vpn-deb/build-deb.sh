#!/bin/bash
# build-deb.sh — Compila o pacote rpa4all-vpn_<version>_all.deb
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="${SCRIPT_DIR}/rpa4all-vpn"
VERSION=$(grep "^Version:" "${PKG_DIR}/DEBIAN/control" | awk '{print $2}')
OUTPUT="${SCRIPT_DIR}/rpa4all-vpn_${VERSION}_all.deb"

echo "Building rpa4all-vpn v${VERSION}..."

# Permissões corretas
chmod 755 "${PKG_DIR}/DEBIAN/postinst"
chmod 755 "${PKG_DIR}/DEBIAN/prerm"
chmod 755 "${PKG_DIR}/DEBIAN/postrm"
chmod 755 "${PKG_DIR}/usr/bin/rpa4all-vpn"
chmod 755 "${PKG_DIR}/usr/bin/rpa4all-vpn-update-endpoint"
chmod 644 "${PKG_DIR}/DEBIAN/control"
chmod 644 "${PKG_DIR}/usr/share/rpa4all-vpn/"*

# Copiar unit files para local de instalação via postinst (não direto em /etc)
# O postinst copia para /etc/systemd/system/

# Build
dpkg-deb --root-owner-group --build "${PKG_DIR}" "${OUTPUT}"

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  Pacote gerado: $(basename "${OUTPUT}")    "
echo "║  Tamanho: $(du -h "${OUTPUT}" | cut -f1)                        "
echo "║                                            "
echo "║  Instalar: sudo dpkg -i ${OUTPUT}          "
echo "║  Remover:  sudo apt remove rpa4all-vpn     "
echo "║  Purge:    sudo dpkg --purge rpa4all-vpn   "
echo "╚════════════════════════════════════════════╝"
