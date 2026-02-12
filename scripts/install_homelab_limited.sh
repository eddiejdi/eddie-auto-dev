#!/bin/sh
# install_homelab_limited.sh
# Gera /etc/sudoers.d/homelab-limited (permitir leitura de logs cloudflared)
# Deve ser executado como root (ou via sudo por outro admin)
set -euo pipefail

cat > /etc/sudoers.d/homelab-limited <<'EOF'
# Sudoers limitado para o usuário homelab — permite apenas leitura de logs/status
Cmnd_Alias CLOUDFLARE_CMDS = \
  /usr/bin/journalctl -u cloudflared.service --no-pager, \
  /usr/bin/systemctl status cloudflared.service, \
  /usr/bin/less /var/log/cloudflared.log

Defaults:homelab !setenv
homelab ALL=(root) NOPASSWD: NOEXEC: CLOUDFLARE_CMDS
EOF

chmod 0440 /etc/sudoers.d/homelab-limited
# Validate
if visudo -cf /etc/sudoers.d/homelab-limited; then
  echo "OK: /etc/sudoers.d/homelab-limited created and validated"
else
  echo "ERROR: visudo validation failed" >&2
  exit 2
fi

# Show summary
echo "--- sudoers file ---"
sed -n '1,120p' /etc/sudoers.d/homelab-limited || true
echo "--- sudo -l homelab (if homelab is logged-in) ---"
if id homelab >/dev/null 2>&1; then
  sudo -l -U homelab || true
else
  echo "User 'homelab' not found locally"
fi

exit 0
