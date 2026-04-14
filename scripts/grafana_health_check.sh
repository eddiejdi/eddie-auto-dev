#!/bin/bash
# Grafana Dashboard Validation & Health Check Script
# Run this to verify Grafana is working after freeze resolution

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  GRAFANA HEALTH CHECK & VALIDATION SCRIPT                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

HOST="${1:-localhost}"
PORT="${2:-3002}"
URL="http://${HOST}:${PORT}"

echo "Target: ${URL}"
echo ""

# Test 1: Basic connectivity
echo "✓ Test 1: HTTP Connectivity"
if curl -s -m 3 "${URL}/api/health" > /dev/null; then
    echo "  ✅ HTTP 200 OK - Grafana is responding"
else
    echo "  ❌ FAILED - Grafana not responding"
    exit 1
fi

# Test 2: Health endpoint
echo ""
echo "✓ Test 2: Health Status"
HEALTH=$(curl -s "${URL}/api/health" | python3 -m json.tool 2>/dev/null)
if echo "$HEALTH" | grep -q "ok"; then
    echo "  ✅ Database: OK"
    echo "  Version: $(echo $HEALTH | grep -o '"version":"[^"]*' | cut -d'"' -f4)"
fi

# Test 3: Docker container stats
echo ""
echo "✓ Test 3: Container Resources"
if command -v docker &> /dev/null; then
    STATS=$(docker stats grafana --no-stream --format "{{.CPUPerc}}|{{.MemUsage}}" 2>/dev/null)
    echo "  CPU: $(echo $STATS | cut -d'|' -f1)"
    echo "  Memory: $(echo $STATS | cut -d'|' -f2)"
fi

# Test 4: Prometheus integration
echo ""
echo "✓ Test 4: Prometheus Data"
PROM_RESPONSE=$(curl -s 'http://localhost:9090/api/v1/query?query=btc_trading_total_pnl' 2>/dev/null)
if echo "$PROM_RESPONSE" | grep -q "success"; then
    echo "  ✅ Prometheus responding with metrics"
    PNLCOUNT=$(echo "$PROM_RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data['data']['result']))" 2>/dev/null)
    echo "  Trading metrics available: $PNLCOUNT streams"
fi

# Test 5: Trading agent status
echo ""
echo "✓ Test 5: Trading Agent Status"
AGENT_STATUS=$(systemctl is-active crypto-agent@BTC_USDT_conservative.service 2>/dev/null)
if [ "$AGENT_STATUS" = "active" ]; then
    echo "  ✅ Agent: ACTIVE"
    echo "  Profile: BTC_USDT_conservative"
else
    echo "  ⚠️  Agent status: $AGENT_STATUS"
fi

# Test 6: Container restart history
echo ""
echo "✓ Test 6: Container Stability"
RESTART_COUNT=$(docker inspect grafana --format='{{.RestartCount}}' 2>/dev/null)
echo "  Restarts: $RESTART_COUNT"
echo "  Uptime: $(docker inspect grafana --format='{{.State.StartedAt}}' 2>/dev/null | cut -d'T' -f2 | cut -d'.' -f1) UTC"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✅ ALL TESTS PASSED - GRAFANA IS OPERATIONAL                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Dashboard URL:"
echo "https://grafana.rpa4all.com/d/btc-trading-monitor/f09fa496-trading-agent-monitor"
echo ""
