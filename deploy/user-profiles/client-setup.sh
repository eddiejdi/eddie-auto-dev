#!/usr/bin/env bash
set -euo pipefail

# Script template para configurar cliente Linux: SSSD + autofs + pam_mkhomedir
# Execute com sudo em um cliente de teste.

LDAP_URI="${LDAP_URI:-ldap://192.168.15.2}"
BASE_DN="${BASE_DN:-dc=rpa4all,dc=com}"
NFS_SERVER="${NFS_SERVER:-192.168.15.2}"
NFS_EXPORT="${NFS_EXPORT:-/srv/home}"

if [[ $(id -u) -ne 0 ]]; then
  echo "Execute como root: sudo $0"
  exit 1
fi

echo "Instalando pacotes necessários (Debian/Ubuntu)..."
apt-get update
apt-get install -y sssd libnss-sss libpam-sss autofs nfs-common libpam-mkhomedir || true

SSSD_CONF="/etc/sssd/sssd.conf"
if [[ ! -f "$SSSD_CONF" ]]; then
  cat > "$SSSD_CONF" <<EOF
[sssd]
services = nss, pam
config_file_version = 2
domains = AUTH

[domain/AUTH]
id_provider = ldap
auth_provider = ldap
ldap_uri = ${LDAP_URI}
ldap_search_base = ${BASE_DN}
ldap_schema = rfc2307
cache_credentials = True
enumerate = False
ldap_tls_reqcert = never
fallback_homedir = /home/%u
default_shell = /bin/bash
EOF
  chmod 600 "$SSSD_CONF"
  echo "sssd.conf criado em $SSSD_CONF (edite bind DN/credenciais se necessário)"
fi

echo "Configurando autofs (/etc/auto.master e /etc/auto.home)"
MASTER_FILE="/etc/auto.master"
MAP_FILE="/etc/auto.home"
grep -q "^/home" "$MASTER_FILE" 2>/dev/null || echo "/home    $MAP_FILE    --timeout=60" >> "$MASTER_FILE"
cat > "$MAP_FILE" <<EOF
*    -fstype=nfs4,rw,soft,intr,vers=4    ${NFS_SERVER}:${NFS_EXPORT}/&
EOF

echo "Habilitando pam_mkhomedir se não existir"
COMMON_SESSION="/etc/pam.d/common-session"
grep -q "pam_mkhomedir.so" "$COMMON_SESSION" 2>/dev/null || echo "session required pam_mkhomedir.so skel=/etc/skel umask=0022" >> "$COMMON_SESSION"

echo "Reiniciando serviços: sssd e autofs"
systemctl restart sssd || true
systemctl restart autofs || true

echo "Validando: getent passwd <username> e ls /home/<username> após login"
echo "Exemplo: getent passwd edenilson"
