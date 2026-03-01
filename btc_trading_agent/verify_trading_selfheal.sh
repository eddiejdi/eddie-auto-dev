#!/bin/bash

# POST-DEPLOYMENT VERIFICATION SCRIPT
# Valida se o trading-selfheal-exporter está funcionando corretamente após deploy

set -e

HOMELAB_HOST="${1:-192.168.15.2}"
SELFHEAL_URL="http://${HOMELAB_HOST}:9121"
METRICS_URL="http://${HOMELAB_HOST}:9120/metrics"
PROMETHEUS_URL="http://${HOMELAB_HOST}:9090"

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

echo -e "${BOLD}=== Trading Self-Heal Post-Deployment Verification ===${NC}\n"

# Test 1: Service is running
echo -ne "[1/10] Checking if trading-selfheal-exporter is running... "
if ssh homelab@${HOMELAB_HOST} "sudo systemctl is-active trading-selfheal-exporter > /dev/null" 2>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  → Fix: ssh homelab@${HOMELAB_HOST} \"sudo systemctl restart trading-selfheal-exporter\""
    ((FAIL++))
fi

# Test 2: Metrics endpoint responds
echo -ne "[2/10] Checking metrics endpoint (port 9120)... "
if curl -s "${METRICS_URL}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  → Fix: curl -s http://${HOMELAB_HOST}:9120/metrics"
    ((FAIL++))
fi

# Test 3: Status endpoint responds
echo -ne "[3/10] Checking status endpoint (port 9121)... "
if curl -s "${SELFHEAL_URL}/status" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
    # Get status details
    PAYLOAD=$(curl -s "${SELFHEAL_URL}/status")
    echo "$PAYLOAD" | jq -r 'keys[] as $key | "  → \($key): up=\(.[$key].up // "N/A"), stalled=\(.[$key].stalled // "N/A")"'
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  → Fix: curl -s http://${HOMELAB_HOST}:9121/status"
    ((FAIL++))
fi

# Test 4: Check all 6 agents in status
echo -ne "[4/10] Verifying all 6 agents are monitored... "
AGENTS=("BTC-USDT" "ETH-USDT" "XRP-USDT" "SOL-USDT" "DOGE-USDT" "ADA-USDT")
STATUS_JSON=$(curl -s "${SELFHEAL_URL}/status" 2>/dev/null || echo "{}")
AGENTS_FOUND=$(echo "$STATUS_JSON" | jq -r 'keys | length')
if [ "$AGENTS_FOUND" -ge 6 ]; then
    echo -e "${GREEN}✓ PASS${NC} (found $AGENTS_FOUND agents)"
    ((PASS++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (found only $AGENTS_FOUND of 6 agents)"
    echo "  → Check if agents are running: ssh homelab@${HOMELAB_HOST} \"systemctl list-units crypto-agent@*\""
    ((FAIL++))
fi

# Test 5: Prometheus targets
echo -ne "[5/10] Checking Prometheus scrape targets... "
PROM_TARGETS=$(curl -s "${PROMETHEUS_URL}/api/v1/targets" 2>/dev/null | jq '.data.activeTargets[] | select(.labels.job=="trading-selfheal" or .labels.job=="crypto-exporters")' | wc -l)
if [ "$PROM_TARGETS" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS${NC} ($PROM_TARGETS targets)"
    ((PASS++))
    # Show target health
    curl -s "${PROMETHEUS_URL}/api/v1/targets" | jq '.data.activeTargets[] | select(.labels.job=="trading-selfheal" or .labels.job=="crypto-exporters") | {job: .labels.job, instance: .labels.instance, health: .health}' | head -12
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  → Fix: Check if Prometheus config was updated"
    echo "  → ssh homelab@${HOMELAB_HOST} \"grep crypto-exporters /etc/prometheus/prometheus.yml\""
    ((FAIL++))
fi

# Test 6: PostgreSQL connectivity
echo -ne "[6/10] Checking PostgreSQL connection... "
PSQL_TEST=$(ssh homelab@${HOMELAB_HOST} "psql -h 192.168.15.2 -p 5433 -U postgres -d postgres -c 'SELECT 1' 2>&1" || echo "FAIL")
if echo "$PSQL_TEST" | grep -q "1 row"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  → PostgreSQL not accessible from homelab"
    echo "  → Verify: ssh homelab@${HOMELAB_HOST} \"nc -zv 192.168.15.2 5433\""
    ((FAIL++))
fi

# Test 7: Ollama connectivity
echo -ne "[7/10] Checking Ollama endpoint... "
OLLAMA_TEST=$(curl -s "http://${HOMELAB_HOST}:11434/api/tags" 2>/dev/null | jq -r '.models[0].name // "N/A"')
if [ "$OLLAMA_TEST" != "N/A" ] && [ -n "$OLLAMA_TEST" ]; then
    echo -e "${GREEN}✓ PASS${NC} (model: $OLLAMA_TEST)"
    ((PASS++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Ollama may be unreachable or no models)"
    echo "  → Check: curl -s http://${HOMELAB_HOST}:11434/api/tags"
    echo "  → Device memory: ssh homelab@${HOMELAB_HOST} \"nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader\""
fi

# Test 8: Audit log exists
echo -ne "[8/10] Checking audit log file... "
AUDIT_EXISTS=$(ssh homelab@${HOMELAB_HOST} "test -f /var/lib/eddie/trading-heal/trading_heal_audit.jsonl && echo 'yes' || echo 'no'")
if [ "$AUDIT_EXISTS" = "yes" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
    # Show recent entries
    AUDIT_COUNT=$(ssh homelab@${HOMELAB_HOST} "wc -l /var/lib/eddie/trading-heal/trading_heal_audit.jsonl" | awk '{print $1}')
    echo "  → Audit log entries: $AUDIT_COUNT"
    echo "  → Recent events:"
    ssh homelab@${HOMELAB_HOST} "tail -5 /var/lib/eddie/trading-heal/trading_heal_audit.jsonl | jq -r '{ts: .timestamp, action: .action, symbol: .symbol, msg: .detail}'" | sed 's/^/    /'
else
    echo -e "${YELLOW}⚠ WARNING${NC} (audit log not yet created)"
    echo "  → This is normal if exporter just started - wait 30 seconds"
fi

# Test 9: Prometheus alert rules loaded
echo -ne "[9/10] Checking prometheus alert rules... "
RULES_LOADED=$(curl -s "${PROMETHEUS_URL}/api/v1/rules" 2>/dev/null | jq '.data.groups[] | select(.name=="trading_agent_alerts") | .rules | length')
if [ -n "$RULES_LOADED" ] && [ "$RULES_LOADED" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS${NC} ($RULES_LOADED rules)"
    ((PASS++))
    curl -s "${PROMETHEUS_URL}/api/v1/rules" | jq '.data.groups[] | select(.name=="trading_agent_alerts") | .rules[].alert' | head -5 | sed 's/^/    /'
else
    echo -e "${YELLOW}⚠ WARNING${NC} (no trading alert rules loaded)"
    echo "  → Fix: Check prometheus.yml - rule_files should include alert_rules.yml"
    echo "  → ssh homelab@${HOMELAB_HOST} \"grep rule_files /etc/prometheus/prometheus.yml\""
fi

# Test 10: Service logs
echo -ne "[10/10] Checking service logs for errors... "
LOG_ERRORS=$(ssh homelab@${HOMELAB_HOST} "journalctl -u trading-selfheal-exporter -n 50 | grep -i error | wc -l")
if [ "$LOG_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASS++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} ($LOG_ERRORS errors in logs)"
    echo "  → Recent logs:"
    ssh homelab@${HOMELAB_HOST} "journalctl -u trading-selfheal-exporter -n 20" | tail -10 | sed 's/^/    /'
fi

# Summary
echo -e "\n${BOLD}=== Verification Summary ===${NC}"
echo -e "Passed: ${GREEN}$PASS/10${NC}"
echo -e "Failed: ${RED}$FAIL/10${NC}"

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}${BOLD}✓ All checks passed! Self-healing is ready.${NC}"
    exit 0
elif [ $FAIL -le 3 ]; then
    echo -e "\n${YELLOW}${BOLD}⚠ Some checks failed, but service may be functional.${NC}"
    echo "Review failures above and fix as needed."
    exit 1
else
    echo -e "\n${RED}${BOLD}✗ Critical failures detected. Review deployment.${NC}"
    exit 1
fi
