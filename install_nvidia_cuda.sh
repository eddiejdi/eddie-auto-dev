#!/bin/bash
# Install NVIDIA CUDA drivers and enable GPU support for Ollama on homelab
# Run on: homelab@192.168.15.2

set -e

echo "============================================================"
echo "🔧 INSTALLLING NVIDIA CUDA DRIVERS & GPU SUPPORT"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Update system
echo -e "${YELLOW}[1/6]${NC} Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Step 2: Install build essentials
echo -e "${YELLOW}[2/6]${NC} Installing build tools..."
sudo apt install -y build-essential linux-headers-$(uname -r) dkms

# Step 3: Check for nvidia-driver-550 availability
echo -e "${YELLOW}[3/6]${NC} Installing NVIDIA drivers (550 recommended for RTX 2060)..."
if sudo apt-cache search nvidia-driver | grep -q nvidia-driver-550; then
    echo "  Found nvidia-driver-550"
    sudo apt install -y nvidia-driver-550
elif sudo apt-cache search nvidia-driver | grep -q nvidia-driver-545; then
    echo "  Found nvidia-driver-545 (alternative)"
    sudo apt install -y nvidia-driver-545
else
    echo -e "${RED}  WARNING: Installing latest available driver${NC}"
    sudo apt install -y nvidia-driver-latest
fi

# Step 4: Install CUDA Toolkit
echo -e "${YELLOW}[4/6]${NC} Installing CUDA Toolkit..."
sudo apt install -y nvidia-cuda-toolkit

# Step 5: Configure Ollama for CUDA
echo -e "${YELLOW}[5/6]${NC} Configuring Ollama systemd service..."
sudo mkdir -p /etc/systemd/system/ollama.service.d

# Create CUDA config drop-in
sudo tee /etc/systemd/system/ollama.service.d/cuda.conf > /dev/null <<'EOF'
# Enable CUDA GPU acceleration for Ollama
[Service]
Environment="PATH=/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="CUDA_HOME=/usr/local/cuda"
Environment="OLLAMA_GPU_MEMORY=6000"
EOF

# Step 6: Reload and restart
echo -e "${YELLOW}[6/6]${NC} Reloading systemd and restarting Ollama..."
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Check results
echo ""
echo "============================================================"
echo "✅ INSTALLATION COMPLETE - Verifying..."
echo "============================================================"
echo ""

sleep 3

# Test nvidia-smi
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ nvidia-smi available${NC}"
    nvidia-smi
    echo ""
else
    echo -e "${RED}✗ nvidia-smi NOT found (reboot may be required)${NC}"
fi

# Test CUDA
if [ -d "/usr/local/cuda" ]; then
    echo -e "${GREEN}✓ CUDA Toolkit installed at /usr/local/cuda${NC}"
    echo "  CUDA version: $(/usr/local/cuda/bin/nvcc --version | head -1)"
    echo ""
fi

# Check Ollama status
echo -e "${YELLOW}Ollama Service Status:${NC}"
sudo systemctl status ollama --no-pager | head -20
echo ""

# Test inference
echo -e "${YELLOW}Testing Ollama with GPU...${NC}"
curl -s http://localhost:11434/api/ps | python3 -m json.tool | head -30

echo ""
echo "============================================================"
echo "🎯 NEXT STEPS:"
echo "============================================================"
echo ""
echo "1. If nvidia-smi shows RTX 2060 → GPU is working ✅"
echo "2. Test LLM speed: python3 measure_ollama_latency.py"
echo "3. Expected improvement: 10x faster than CPU"
echo ""
echo "⚠️  If nvidia-smi still shows 'No devices found':"
echo "   • Reboot the system: sudo reboot"
echo "   • Check BIOS for PCIe settings (ensure GPU enabled)"
echo "   • Try: sudo apt install --reinstall cuda-drivers"
echo ""
