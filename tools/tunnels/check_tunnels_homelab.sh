#!/usr/bin/env bash
set -euo pipefail

echo "# Check Tunnels - homelab ($(hostname -f 2>/dev/null || hostname))"
echo

run() { 
  echo "+ $@" >&2
  "$@"
}

echo "=== SYSTEMD: list relevant services ==="
sudo systemctl list-units --type=service --all | grep -E 'cloudflared|openwebui-ssh-tunnel|localtunnel|cloudflared-named' || true
echo

echo "=== SYSTEMD: status for expected services ==="
for svc in openwebui-ssh-tunnel cloudflared; do
  echo "--- $svc ---"
  sudo systemctl status "$svc" --no-pager || echo "(no unit or failed to query $svc)"
  echo
done

echo "=== SYSTEMD: template instances (if any) ==="
sudo systemctl list-units --type=service --all | egrep 'cloudflared-named@|localtunnel@' || true
echo

echo "=== cloudflared CLI (if installed) ==="
if command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared found: $(command -v cloudflared)"
  cloudflared tunnel list || echo "(cloudflared tunnel list failed)"
else
  echo "cloudflared not installed"
fi
echo

echo "=== SSH reverse tunnels (ssh processes with -R) ==="
ps auxww | egrep "ssh .* -R" || echo "(no ssh -R processes found)"
echo

echo "=== Listening sockets of interest ==="
echo "-- TCP listeners (filtered) --"
if sudo ss -ltnp 2>/dev/null >/dev/null 2>&1; then
  sudo ss -ltnp 2>/dev/null | egrep '13300|cloudflared|ssh|3000' || true
else
  sudo netstat -ltnp 2>/dev/null | egrep '13300|cloudflared|ssh|3000' || true
fi
echo

echo "=== lsof (requires root) for ports 13300/3000 ==="
if command -v lsof >/dev/null 2>&1; then
  sudo lsof -iTCP -sTCP:LISTEN -P -n | egrep ':(13300|3000)\b|cloudflared|ssh' || echo "(no lsof matches)"
else
  echo "lsof not installed"
fi
echo

echo "=== Nginx (if present) ==="
if command -v nginx >/dev/null 2>&1; then
  sudo systemctl status nginx --no-pager || true
  echo "-- nginx test config --"
  sudo nginx -t || true
else
  echo "nginx not installed"
fi
echo

echo "=== Quick HTTP check (local reverse endpoint) ==="
curl -I --max-time 5 http://127.0.0.1:13300 2>/dev/null || echo "(no HTTP response from 127.0.0.1:13300)"
echo

echo "=== DONE ==="
