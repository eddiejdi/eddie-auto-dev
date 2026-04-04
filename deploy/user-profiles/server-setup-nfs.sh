#!/usr/bin/env bash
set -euo pipefail

# Script template: configurar export NFS para /srv/home
# Execute no servidor homelab como root (sudo).

EXPORT_DIR="/srv/home"
NETWORK_CIDR="${NETWORK_CIDR:-192.168.15.0/24}"
EXPORTS_FILE="/etc/exports"
BACKUP_FILE="${EXPORTS_FILE}.bak.$(date +%Y%m%d_%H%M%S)"

if [[ $(id -u) -ne 0 ]]; then
  echo "Execute este script como root: sudo $0"
  exit 1
fi

mkdir -p "$EXPORT_DIR"
chown root:root "$EXPORT_DIR"
chmod 0755 "$EXPORT_DIR"

echo "Fazendo backup de $EXPORTS_FILE → $BACKUP_FILE"
cp "$EXPORTS_FILE" "$BACKUP_FILE" || true

echo "Adicionando export de $EXPORT_DIR para $NETWORK_CIDR"
grep -q "^$EXPORT_DIR" "$EXPORTS_FILE" 2>/dev/null || cat >> "$EXPORTS_FILE" <<EOF
$EXPORT_DIR    $NETWORK_CIDR(rw,sync,root_squash,subtree_check)
EOF

echo "Aplicando exportfs -ra"
exportfs -ra

echo "Shares exportados:" 
showmount -e 127.0.0.1 || true

echo "Observações de deploy:"
echo " - Ajuste root_squash conforme sua política (desativar aumenta risco)."
echo " - Caso existam clientes Windows, considere adicionar um compartilhamento Samba."
echo " - Configure firewall: permitir NFS (2049/tcp/udp) e portas rpcbind se necessário."

echo "Concluído. Teste em um cliente: showmount -e <IP_DO_SERVIDOR>"
