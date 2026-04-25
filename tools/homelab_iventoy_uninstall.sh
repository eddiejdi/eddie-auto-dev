#!/bin/bash
# Script de desinstalação do iVentoy com backup prévio
# Uso: ./homelab_iventoy_uninstall.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  DESINSTALAR IVENTOY                                      ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Validar que backup existe
BACKUP_DIR=$(ls -dt /home/homelab/backups/iventoy_backup_* 2>/dev/null | head -1)
if [ -z "$BACKUP_DIR" ]; then
  echo "❌ Nenhum backup encontrado em /home/homelab/backups/iventoy_backup_*"
  echo "Aborting..."
  exit 1
fi
echo "✓ Backup validado: $BACKUP_DIR"

echo ""
echo "== Parar serviço iVentoy =="
sudo systemctl stop iventoy.service 2>/dev/null || true
sleep 2
echo "✓ Serviço parado"

echo ""
echo "== Finalizar processos pendentes =="
sudo pkill -9 -f "iventoy" 2>/dev/null || true
sleep 1
echo "✓ Processos terminados"

echo ""
echo "== Remover instalação =="
sudo rm -rf /opt/iventoy-1.0.25 2>/dev/null || true
sudo rm -rf /opt/iventoy 2>/dev/null || true
echo "✓ Diretórios removidos"

echo ""
echo "== Desabilitar serviço =="
sudo systemctl disable iventoy.service 2>/dev/null || true
echo "✓ Serviço desabilitado"

echo ""
echo "== Verificar remoção =="
if ! ls /opt/iventoy* 2>/dev/null >/dev/null; then
  echo "✓ /opt/iventoy completamente removido"
else
  echo "⚠️  /opt/iventoy ainda existe"
fi

echo ""
echo "✅ DESINSTALAÇÃO COMPLETA"
echo "Backup preservado em: $BACKUP_DIR"
