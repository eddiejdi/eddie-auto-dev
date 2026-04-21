#!/bin/bash
# Grafana + Prometheus Emergency Recovery Script
# Use: bash grafana_recover.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   GRAFANA + PROMETHEUS RECOVERY SCRIPT                    ║${NC}"
echo -e "${YELLOW}║   Date: $(date '+%Y-%m-%d %H:%M:%S')                              ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Detect environment
echo -e "${YELLOW}[1/5]${NC} Detecting environment..."
USE_DOCKER=0
USE_SYSTEMD=0

if command -v docker &> /dev/null; then
    if docker ps &> /dev/null 2>&1; then
        USE_DOCKER=1
        echo -e "${GREEN}✅${NC} Docker detected"
    fi
fi

if command -v systemctl &> /dev/null; then
    if systemctl is-active grafana-server &> /dev/null 2>&1 || systemctl is-enabled grafana-server &> /dev/null 2>&1; then
        USE_SYSTEMD=1
        echo -e "${GREEN}✅${NC} Systemd detected (grafana-server)"
    fi
fi

if [ $USE_DOCKER -eq 0 ] && [ $USE_SYSTEMD -eq 0 ]; then
    echo -e "${RED}❌${NC} No Docker or systemd services found. Exiting."
    exit 1
fi

echo ""

# Step 2: Check current status
echo -e "${YELLOW}[2/5]${NC} Checking current status..."

if [ $USE_DOCKER -eq 1 ]; then
    GRAFANA_STATUS=$(docker ps --filter name=grafana --format "{{.Status}}" 2>/dev/null || echo "not found")
    PROM_STATUS=$(docker ps --filter name=prometheus --format "{{.Status}}" 2>/dev/null || echo "not found")
    echo "  Grafana: $GRAFANA_STATUS"
    echo "  Prometheus: $PROM_STATUS"
fi

if [ $USE_SYSTEMD -eq 1 ]; then
    GRAFANA_STATUS=$(systemctl is-active grafana-server 2>/dev/null || echo "inactive")
    echo "  Grafana (systemd): $GRAFANA_STATUS"
fi

echo ""

# Step 3: Restart services
echo -e "${YELLOW}[3/5]${NC} Restarting services..."

if [ $USE_DOCKER -eq 1 ]; then
    echo "  Restarting Docker containers..."
    docker restart grafana 2>/dev/null && echo -e "  ${GREEN}✅${NC} grafana restarted" || echo -e "  ${RED}❌${NC} grafana restart failed"
    docker restart prometheus 2>/dev/null && echo -e "  ${GREEN}✅${NC} prometheus restarted" || echo -e "  ${RED}❌${NC} prometheus restart failed"
    sleep 5
fi

if [ $USE_SYSTEMD -eq 1 ]; then
    echo "  Restarting systemd services..."
    sudo systemctl restart grafana-server 2>/dev/null && echo -e "  ${GREEN}✅${NC} grafana-server restarted" || echo -e "  ${RED}❌${NC} grafana-server restart failed"
    sudo systemctl restart prometheus 2>/dev/null && echo -e "  ${GREEN}✅${NC} prometheus restarted" || echo -e "  ${RED}❌${NC} prometheus restart failed"
    sleep 5
fi

echo ""

# Step 4: Verify health
echo -e "${YELLOW}[4/5]${NC} Verifying services..."

# Test Grafana
if timeout 5 curl -s -I http://localhost:3002/api/health &> /dev/null; then
    echo -e "  ${GREEN}✅${NC} Grafana health check passed (localhost:3002)"
else
    echo -e "  ${RED}❌${NC} Grafana health check failed"
fi

# Test Prometheus
if timeout 5 curl -s -I http://localhost:9090/-/healthy &> /dev/null; then
    echo -e "  ${GREEN}✅${NC} Prometheus health check passed (localhost:9090)"
else
    echo -e "  ${RED}❌${NC} Prometheus health check failed"
fi

echo ""

# Step 5: Final summary
echo -e "${YELLOW}[5/5]${NC} Recovery complete!"
echo ""

# Show running containers/services
if [ $USE_DOCKER -eq 1 ]; then
    echo -e "${YELLOW}Running Containers:${NC}"
    docker ps --filter "name=grafana\|prometheus" --format "table {{.Names}}\t{{.Status}}"
    echo ""
fi

if [ $USE_SYSTEMD -eq 1 ]; then
    echo -e "${YELLOW}Systemd Services:${NC}"
    systemctl status grafana-server --no-paging 2>/dev/null | grep "Active:" || echo "N/A"
    echo ""
fi

echo -e "${GREEN}✅ Recovery script complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test access: curl http://localhost:3002"
echo "2. Check dashboard: http://192.168.15.2:3002 (from workstation)"
echo "3. Verify metrics: http://192.168.15.2:9090"
echo ""

exit 0
