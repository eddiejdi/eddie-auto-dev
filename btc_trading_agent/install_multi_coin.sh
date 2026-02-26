#!/bin/bash
# Install Multi-Coin Trading Services
set -e

SYSTEMD_DIR="/etc/systemd/system"
SRC_DIR="/home/homelab/myClaude/btc_trading_agent/systemd"

echo "📦 Installing systemd template units..."
sudo cp "$SRC_DIR/crypto-agent@.service" "$SYSTEMD_DIR/"
sudo cp "$SRC_DIR/crypto-api@.service" "$SYSTEMD_DIR/"
sudo cp "$SRC_DIR/crypto-exporter@.service" "$SYSTEMD_DIR/"

# --- ETH-USDT ---
echo "🪙 Installing ETH-USDT..."
sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@ETH_USDT.service.d"
sudo cp "$SRC_DIR/crypto-agent@ETH_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@ETH_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-api@ETH_USDT.service.d"
sudo cp "$SRC_DIR/crypto-api@ETH_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@ETH_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@ETH_USDT.service.d"
sudo cp "$SRC_DIR/crypto-exporter@ETH_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@ETH_USDT.service.d/"

# --- XRP-USDT ---
echo "🪙 Installing XRP-USDT..."
sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@XRP_USDT.service.d"
sudo cp "$SRC_DIR/crypto-agent@XRP_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@XRP_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-api@XRP_USDT.service.d"
sudo cp "$SRC_DIR/crypto-api@XRP_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@XRP_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@XRP_USDT.service.d"
sudo cp "$SRC_DIR/crypto-exporter@XRP_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@XRP_USDT.service.d/"

# --- SOL-USDT ---
echo "🪙 Installing SOL-USDT..."
sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@SOL_USDT.service.d"
sudo cp "$SRC_DIR/crypto-agent@SOL_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@SOL_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-api@SOL_USDT.service.d"
sudo cp "$SRC_DIR/crypto-api@SOL_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@SOL_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@SOL_USDT.service.d"
sudo cp "$SRC_DIR/crypto-exporter@SOL_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@SOL_USDT.service.d/"

# --- DOGE-USDT ---
echo "🪙 Installing DOGE-USDT..."
sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@DOGE_USDT.service.d"
sudo cp "$SRC_DIR/crypto-agent@DOGE_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@DOGE_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-api@DOGE_USDT.service.d"
sudo cp "$SRC_DIR/crypto-api@DOGE_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@DOGE_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@DOGE_USDT.service.d"
sudo cp "$SRC_DIR/crypto-exporter@DOGE_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@DOGE_USDT.service.d/"

# --- ADA-USDT ---
echo "🪙 Installing ADA-USDT..."
sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@ADA_USDT.service.d"
sudo cp "$SRC_DIR/crypto-agent@ADA_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@ADA_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-api@ADA_USDT.service.d"
sudo cp "$SRC_DIR/crypto-api@ADA_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@ADA_USDT.service.d/"
sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@ADA_USDT.service.d"
sudo cp "$SRC_DIR/crypto-exporter@ADA_USDT.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@ADA_USDT.service.d/"

echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable and start new coin services
echo "🚀 Starting ETH-USDT..."
sudo systemctl enable --now crypto-agent@ETH_USDT.service
sudo systemctl enable --now crypto-exporter@ETH_USDT.service
# sudo systemctl enable --now crypto-api@ETH_USDT.service

echo "🚀 Starting XRP-USDT..."
sudo systemctl enable --now crypto-agent@XRP_USDT.service
sudo systemctl enable --now crypto-exporter@XRP_USDT.service
# sudo systemctl enable --now crypto-api@XRP_USDT.service

echo "🚀 Starting SOL-USDT..."
sudo systemctl enable --now crypto-agent@SOL_USDT.service
sudo systemctl enable --now crypto-exporter@SOL_USDT.service
# sudo systemctl enable --now crypto-api@SOL_USDT.service

echo "🚀 Starting DOGE-USDT..."
sudo systemctl enable --now crypto-agent@DOGE_USDT.service
sudo systemctl enable --now crypto-exporter@DOGE_USDT.service
# sudo systemctl enable --now crypto-api@DOGE_USDT.service

echo "🚀 Starting ADA-USDT..."
sudo systemctl enable --now crypto-agent@ADA_USDT.service
sudo systemctl enable --now crypto-exporter@ADA_USDT.service
# sudo systemctl enable --now crypto-api@ADA_USDT.service

echo ""
echo "✅ Multi-coin services installed!"
echo ""
echo "Status:"
systemctl is-active crypto-agent@ETH_USDT.service && echo "  ✅ ETH-USDT agent" || echo "  ❌ ETH-USDT agent"
systemctl is-active crypto-exporter@ETH_USDT.service && echo "  ✅ ETH-USDT exporter" || echo "  ❌ ETH-USDT exporter"
systemctl is-active crypto-agent@XRP_USDT.service && echo "  ✅ XRP-USDT agent" || echo "  ❌ XRP-USDT agent"
systemctl is-active crypto-exporter@XRP_USDT.service && echo "  ✅ XRP-USDT exporter" || echo "  ❌ XRP-USDT exporter"
systemctl is-active crypto-agent@SOL_USDT.service && echo "  ✅ SOL-USDT agent" || echo "  ❌ SOL-USDT agent"
systemctl is-active crypto-exporter@SOL_USDT.service && echo "  ✅ SOL-USDT exporter" || echo "  ❌ SOL-USDT exporter"
systemctl is-active crypto-agent@DOGE_USDT.service && echo "  ✅ DOGE-USDT agent" || echo "  ❌ DOGE-USDT agent"
systemctl is-active crypto-exporter@DOGE_USDT.service && echo "  ✅ DOGE-USDT exporter" || echo "  ❌ DOGE-USDT exporter"
systemctl is-active crypto-agent@ADA_USDT.service && echo "  ✅ ADA-USDT agent" || echo "  ❌ ADA-USDT agent"
systemctl is-active crypto-exporter@ADA_USDT.service && echo "  ✅ ADA-USDT exporter" || echo "  ❌ ADA-USDT exporter"
