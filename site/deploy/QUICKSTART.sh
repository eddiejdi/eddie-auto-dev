#!/bin/bash
# Quick deployment - Run on homelab server (192.168.15.2)

echo "🚀 RPA4ALL IDE - Cloudflare Tunnel Quick Deploy"
echo "================================================"
echo ""
echo "This will:"
echo "  ✅ Configure Cloudflare Tunnel for external access"
echo "  ✅ Expose IDE, APIs, and dashboards securely"
echo "  ✅ No router port forwarding needed"
echo ""

# Navigate to deploy folder
cd "$(dirname "$0")"

# Run setup
sudo ./setup_cloudflared_ide.sh

echo ""
echo "================================================"
echo "✅ Setup complete!"
echo ""
echo "Your IDE is now accessible:"
echo "  • Locally:    http://192.168.15.2:8081"
echo "  • Externally: https://ide.rpa4all.com"
echo ""
echo "💡 The IDE automatically detects your network"
echo "   and uses the fastest connection available."
echo ""
