#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  printf 'Run this script as root.\n' >&2
  exit 1
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
  printf 'Usage: %s <interface> <dns_server_ip> [--deploy-network]\n' "$0" >&2
  exit 1
fi

iface="$1"
dns_server="$2"
deploy_network="${3:-}"

export LANG=C.UTF-8
export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none

apt-get install --yes systemd-resolved psmisc gnupg wget
systemctl enable --now systemd-resolved.service
systemctl restart systemd-resolved.service
resolvectl dns "${iface}" "${dns_server}"

apt-get install --yes gnupg
wget --quiet --output-document=- https://packages.openmediavault.org/public/archive.key \
  | gpg --dearmor --yes --output /usr/share/keyrings/openmediavault-archive-keyring.gpg

cat >/etc/apt/sources.list.d/openmediavault.list <<'EOF'
deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://packages.openmediavault.org/public synchrony main
# deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://downloads.sourceforge.net/project/openmediavault/packages synchrony main
# deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://packages.openmediavault.org/public synchrony-proposed main
# deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://downloads.sourceforge.net/project/openmediavault/packages synchrony-proposed main
# deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://packages.openmediavault.org/public synchrony partner
# deb [signed-by=/usr/share/keyrings/openmediavault-archive-keyring.gpg] https://downloads.sourceforge.net/project/openmediavault/packages synchrony partner
EOF

apt-get update
apt-get --yes --auto-remove --show-upgraded \
  --allow-downgrades --allow-change-held-packages \
  --no-install-recommends \
  --option DPkg::Options::="--force-confdef" \
  --option DPkg::Options::="--force-confold" \
  install openmediavault

omv-confdbadm populate

if [[ "${deploy_network}" == "--deploy-network" ]]; then
  omv-salt deploy run systemd-networkd
else
  printf '\nOMV installed. Run omv-firstaid or rerun this script with --deploy-network when you are ready.\n'
fi
