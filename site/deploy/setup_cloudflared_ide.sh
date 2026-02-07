#!/bin/bash
# Setup Cloudflare Tunnel for RPA4ALL IDE
# Run this on homelab server (192.168.15.2)

set -e

echo "🌐 RPA4ALL IDE - Cloudflare Tunnel Setup"
echo "========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
TUNNEL_NAME="rpa4all-ide"
CONFIG_FILE="$HOME/.cloudflared/config.yml"
TUNNEL_CONFIG="$(dirname "$0")/cloudflared-rpa4all-ide.yml"

# Check if running as root (needed for systemd service)
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Warning: Not running as root. Will need sudo for service installation.${NC}"
fi

# Step 1: Check if cloudflared is installed
echo ""
echo "📦 Step 1: Checking cloudflared installation..."
if ! command -v cloudflared &> /dev/null; then
    echo -e "${YELLOW}cloudflared not found. Installing...${NC}"

    # Download and install
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb

    echo -e "${GREEN}✅ cloudflared installed!${NC}"
else
    echo -e "${GREEN}✅ cloudflared already installed ($(cloudflared --version))${NC}"
fi

# Step 2: Check authentication
echo ""
echo "🔐 Step 2: Checking Cloudflare authentication..."
if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
    echo -e "${YELLOW}Not authenticated. Opening browser for login...${NC}"
    cloudflared tunnel login
    echo -e "${GREEN}✅ Authenticated!${NC}"
else
    echo -e "${GREEN}✅ Already authenticated${NC}"
fi

# Step 3: Create tunnel (if doesn't exist)
echo ""
echo "🚇 Step 3: Creating tunnel '$TUNNEL_NAME'..."

# Check if tunnel already exists
EXISTING_TUNNEL=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || echo "")

if [ -z "$EXISTING_TUNNEL" ]; then
    cloudflared tunnel create "$TUNNEL_NAME"
    echo -e "${GREEN}✅ Tunnel created!${NC}"
else
    echo -e "${GREEN}✅ Tunnel already exists${NC}"
fi

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
echo -e "Tunnel ID: ${GREEN}$TUNNEL_ID${NC}"

# Step 4: Configure tunnel
echo ""
echo "⚙️  Step 4: Configuring tunnel..."

# Create .cloudflared directory if doesn't exist
mkdir -p "$HOME/.cloudflared"

# Copy template and replace tunnel ID
if [ -f "$TUNNEL_CONFIG" ]; then
    sed "s/<TUNNEL_ID>/$TUNNEL_ID/g" "$TUNNEL_CONFIG" > "$CONFIG_FILE"
    echo -e "${GREEN}✅ Configuration created at: $CONFIG_FILE${NC}"
else
    echo -e "${RED}❌ Template config not found: $TUNNEL_CONFIG${NC}"
    exit 1
fi

# Step 5: Configure DNS routes
echo ""
echo "🌐 Step 5: Configuring DNS routes..."
echo -e "${YELLOW}Setting up DNS records in Cloudflare...${NC}"

# Add DNS records for each hostname
cloudflared tunnel route dns "$TUNNEL_NAME" ide.rpa4all.com 2>/dev/null || echo "DNS for ide.rpa4all.com already exists or failed"
cloudflared tunnel route dns "$TUNNEL_NAME" api.rpa4all.com 2>/dev/null || echo "DNS for api.rpa4all.com already exists or failed"
cloudflared tunnel route dns "$TUNNEL_NAME" openwebui.rpa4all.com 2>/dev/null || echo "DNS for openwebui.rpa4all.com already exists or failed"
cloudflared tunnel route dns "$TUNNEL_NAME" grafana.rpa4all.com 2>/dev/null || echo "DNS for grafana.rpa4all.com already exists or failed"

echo -e "${GREEN}✅ DNS routes configured${NC}"

# Step 6: Install systemd service
echo ""
echo "🔧 Step 6: Installing systemd service..."

if sudo cloudflared service install; then
    echo -e "${GREEN}✅ Service installed${NC}"

    # Enable and start service
    sudo systemctl enable cloudflared
    sudo systemctl restart cloudflared

    echo -e "${GREEN}✅ Service started${NC}"
else
    echo -e "${YELLOW}⚠️  Service might already be installed${NC}"
fi

# Step 7: Check status
echo ""
echo "📊 Step 7: Checking tunnel status..."
sleep 3
sudo systemctl status cloudflared --no-pager -l || true

# Step 8: Test endpoints
echo ""
echo "🧪 Step 8: Testing local endpoints..."
echo "Checking services..."

check_service() {
    local name=$1
    local port=$2
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" | grep -q "200\|302\|404"; then
        echo -e "  ${GREEN}✅ $name (localhost:$port)${NC}"
    else
        echo -e "  ${RED}❌ $name (localhost:$port) - NOT RESPONDING${NC}"
    fi
}

check_service "IDE Static Site" 8081
check_service "Code Runner API" 2000
check_service "Specialized Agents API" 8503
check_service "Open WebUI" 3000
check_service "Grafana" 3001

# Final instructions
echo ""
echo "========================================="
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Your services are now accessible at:"
echo -e "  ${GREEN}• IDE:${NC}          https://ide.rpa4all.com"
echo -e "  ${GREEN}• API:${NC}          https://api.rpa4all.com"
echo -e "  ${GREEN}• Open WebUI:${NC}   https://openwebui.rpa4all.com"
echo -e "  ${GREEN}• Grafana:${NC}      https://grafana.rpa4all.com"
echo ""
echo "Useful commands:"
echo "  • Check logs:     sudo journalctl -u cloudflared -f"
echo "  • Restart tunnel: sudo systemctl restart cloudflared"
echo "  • Stop tunnel:    sudo systemctl stop cloudflared"
echo "  • Tunnel info:    cloudflared tunnel info $TUNNEL_NAME"
echo ""
echo -e "${YELLOW}⚠️  Note: DNS propagation may take a few minutes${NC}"
