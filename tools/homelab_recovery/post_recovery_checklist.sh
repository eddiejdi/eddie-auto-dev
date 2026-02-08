#!/bin/bash
# Post-recovery checklist — executar APÓS o homelab voltar online
# Usage: ssh homelab@192.168.15.2 'bash -s' < tools/homelab_recovery/post_recovery_checklist.sh

set -e
echo "=== Homelab Post-Recovery Checklist ==="
echo "$(date)"
echo ""

# 1. SSH
echo "1. SSH..."
systemctl is-active --quiet sshd && echo "   ✅ sshd active" || echo "   ❌ sshd down"

# 2. Cloudflared
echo "2. Cloudflared..."
systemctl is-active --quiet cloudflared && echo "   ✅ cloudflared active" || {
  echo "   ❌ cloudflared down — restarting..."
  sudo systemctl restart cloudflared
  sleep 3
  systemctl is-active --quiet cloudflared && echo "   ✅ cloudflared restarted" || echo "   ❌ STILL DOWN"
}

# 3. Specialized Agents API
echo "3. Agents API..."
systemctl is-active --quiet specialized-agents-api && echo "   ✅ agents-api active" || {
  echo "   ❌ agents-api down — restarting..."
  sudo systemctl restart specialized-agents-api
  sleep 5
  systemctl is-active --quiet specialized-agents-api && echo "   ✅ agents-api restarted" || echo "   ❌ STILL DOWN"
}

# 4. PostgreSQL (Docker)
echo "4. PostgreSQL..."
if docker ps --format '{{.Names}}' | grep -q eddie-postgres; then
  echo "   ✅ eddie-postgres running"
else
  echo "   ❌ eddie-postgres not running — starting..."
  docker start eddie-postgres 2>/dev/null || \
  docker run -d --name eddie-postgres --restart unless-stopped \
    -e POSTGRES_PASSWORD=eddie_memory_2026 -p 5432:5432 postgres:15-alpine
  sleep 3
  docker ps --format '{{.Names}}' | grep -q eddie-postgres && echo "   ✅ started" || echo "   ❌ FAILED"
fi

# 5. Git repos alignment
echo "5. Git repos..."
for d in ~/eddie-auto-dev ~/agents_workspace/dev ~/agents_workspace/cer ~/agents_workspace/prod; do
  if [ -d "$d/.git" ]; then
    cd "$d"
    git fetch origin 2>/dev/null
    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    REMOTE=$(git rev-parse origin/main 2>/dev/null)
    if [ "$LOCAL" = "$REMOTE" ]; then
      echo "   ✅ $d up-to-date ($LOCAL)"
    else
      echo "   ⚠️  $d behind — pulling..."
      git reset --hard origin/main 2>/dev/null
      echo "   ✅ $d updated to $(git rev-parse HEAD)"
    fi
  fi
done

# 6. Install SSH safeguard cron
echo "6. SSH Safeguard..."
if sudo crontab -l 2>/dev/null | grep -q homelab-ssh-safeguard; then
  echo "   ✅ Safeguard already installed"
else
  echo "   Installing safeguard..."
  cat > /tmp/homelab-ssh-safeguard.sh << 'EOF'
#!/bin/bash
if ! systemctl is-active --quiet sshd && ! systemctl is-active --quiet ssh; then
  systemctl start sshd 2>/dev/null || systemctl start ssh 2>/dev/null
  logger "homelab-safeguard: SSH restarted"
fi
EOF
  sudo mv /tmp/homelab-ssh-safeguard.sh /usr/local/bin/homelab-ssh-safeguard.sh
  sudo chmod +x /usr/local/bin/homelab-ssh-safeguard.sh
  (sudo crontab -l 2>/dev/null | grep -v homelab-ssh-safeguard; echo "* * * * * /usr/local/bin/homelab-ssh-safeguard.sh") | sudo crontab -
  echo "   ✅ Safeguard installed (cron every minute)"
fi

# 7. WoL enable check
echo "7. WoL..."
IFACE=$(ip route get 1 2>/dev/null | awk '{print $5;exit}')
if command -v ethtool &>/dev/null && [ -n "$IFACE" ]; then
  WOL_STATUS=$(sudo ethtool "$IFACE" 2>/dev/null | grep 'Wake-on' | tail -1 | awk '{print $2}')
  if echo "$WOL_STATUS" | grep -q 'g'; then
    echo "   ✅ WoL enabled on $IFACE ($WOL_STATUS)"
  else
    echo "   ⚠️  WoL not enabled ($WOL_STATUS) — enabling..."
    sudo ethtool -s "$IFACE" wol g 2>/dev/null
    echo "   ✅ WoL enabled (runtime only, add to /etc/network/interfaces for persistence)"
  fi
else
  echo "   ⚠️  ethtool not installed — install with: sudo apt install ethtool"
fi

# 8. Bitwarden CLI
echo "8. Bitwarden..."
if command -v bw &>/dev/null; then
  BW_STATUS=$(bw status 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null)
  echo "   Status: $BW_STATUS"
else
  echo "   ⚠️  bw CLI not installed"
fi

echo ""
echo "=== Checklist complete ==="
