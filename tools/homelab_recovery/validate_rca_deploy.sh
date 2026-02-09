#!/bin/bash
# Validate RCA services on homelab deployment

set -euo pipefail

HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"

echo "=== Validating RCA services on homelab ==="
echo "Host: $HOMELAB_HOST"
echo ""

# Verify systemd user units exist
echo "1. Checking systemd user units..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "systemctl --user list-unit-files | grep agent" || echo "  No agent units found yet"

# Check if services are active
echo ""
echo "2. Checking service status..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "systemctl --user status agent-api.service agent-consumer.service" || echo "  Services not yet active"

# Verify RCA scripts installed
echo ""
echo "3. Checking RCA scripts..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "ls -lh ~/eddie-auto-dev/tools/homelab_recovery/*.py ~/eddie-auto-dev/tools/homelab_recovery/*.sh 2>/dev/null || echo 'Scripts not yet installed'" || true

# Test API endpoint
echo ""
echo "4. Testing agent API endpoint..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "curl -s http://127.0.0.1:8888/rcas | head -c 200" || echo "  API endpoint not responding yet"

# Check agent queue
echo ""
echo "5. Checking agent queue directory..."
ssh "$HOMELAB_USER@$HOMELAB_HOST" "ls -la ~/eddie-auto-dev/.agent_queue/ 2>/dev/null || echo 'Queue directory not yet created'" || true

echo ""
echo "=== Validation complete ==="
