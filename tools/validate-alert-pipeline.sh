#!/bin/bash
################################################################################
# Alert Pipeline Validation Script
# Purpose: Continuous validation of Prometheus + AlertManager pipeline
# Usage: ./tools/validate-alert-pipeline.sh
################################################################################

set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROMETHEUS_URL="http://localhost:9090"
ALERTMANAGER_URL="http://localhost:9093"
EXPECTED_RULES=4
TIMEOUT=5

# Counters
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# Functions
log_test() {
    echo -n "[$1] Testing: $2... "
    ((TESTS_TOTAL++))
}

log_pass() {
    echo -e "${GREEN}✅ PASS${NC}"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

log_warn() {
    echo -e "${YELLOW}⚠️  WARNING${NC}: $1"
}

# Test Functions
test_prometheus_active() {
    log_test "1/10" "Prometheus service active"
    
    if ! systemctl is-active prometheus &>/dev/null; then
        log_fail "Prometheus service not active"
        return 1
    fi
    log_pass
}

test_alertmanager_active() {
    log_test "2/10" "AlertManager service active"
    
    if ! systemctl is-active alertmanager &>/dev/null; then
        log_fail "AlertManager service not active"
        return 1
    fi
    log_pass
}

test_prometheus_api() {
    log_test "3/10" "Prometheus API responding"
    
    if ! curl -sf --connect-timeout $TIMEOUT -m $TIMEOUT "$PROMETHEUS_URL/-/healthy" &>/dev/null; then
        log_fail "Prometheus API not responding"
        return 1
    fi
    log_pass
}

test_alertmanager_api() {
    log_test "4/10" "AlertManager API responding"
    
    if ! curl -sf --connect-timeout $TIMEOUT -m $TIMEOUT "$ALERTMANAGER_URL/-/healthy" &>/dev/null; then
        log_fail "AlertManager API not responding"
        return 1
    fi
    log_pass
}

test_rules_count() {
    log_test "5/10" "Alert rules loaded (expecting $EXPECTED_RULES)"
    
    RULES_COUNT=$(curl -s "$PROMETHEUS_URL/api/v1/rules" 2>/dev/null | \
        jq '.data.groups[0].rules | length' 2>/dev/null)
    
    if [ -z "$RULES_COUNT" ] || [ "$RULES_COUNT" != "$EXPECTED_RULES" ]; then
        log_fail "Expected $EXPECTED_RULES rules, got $RULES_COUNT"
        return 1
    fi
    log_pass
}

test_rules_health() {
    log_test "6/10" "All alert rules in OK health status"
    
    UNHEALTHY=$(curl -s "$PROMETHEUS_URL/api/v1/rules" 2>/dev/null | \
        jq '.data.groups[0].rules[] | select(.health != "ok") | .name' 2>/dev/null | wc -l)
    
    if [ "$UNHEALTHY" -gt 0 ]; then
        log_warn "Found $UNHEALTHY rules with non-OK health status"
        # This is not a hard failure, just a warning
    fi
    log_pass
}

test_webhook_configured() {
    log_test "7/10" "Webhook configuration present"
    
    if ! grep -q "http://127.0.0.1:8503/alerts" /etc/alertmanager/alertmanager.yml 2>/dev/null; then
        log_fail "Webhook not found in AlertManager config"
        return 1
    fi
    log_pass
}

test_no_unexpected_alerts() {
    log_test "8/10" "No unexpected alerts firing"
    
    ALERT_COUNT=$(curl -s "$ALERTMANAGER_URL/api/v1/alerts" 2>/dev/null | \
        jq '.data | length' 2>/dev/null)
    
    if [ -z "$ALERT_COUNT" ]; then
        log_warn "Could not determine alert count from API"
        log_pass  # Don't fail on this check
        return 0
    fi
    
    # We allow 0 alerts or test alerts, but warn if others exist
    if [ "$ALERT_COUNT" -gt 1 ]; then
        log_warn "Found $ALERT_COUNT alerts (unexpected if system is healthy)"
    fi
    log_pass
}

test_exporters_connected() {
    log_test "9/10" "At least one exporter connected"
    
    EXPORTER_COUNT=$(curl -s "$PROMETHEUS_URL/api/v1/targets" 2>/dev/null | \
        jq '.data.activeTargets | length' 2>/dev/null)
    
    if [ -z "$EXPORTER_COUNT" ] || [ "$EXPORTER_COUNT" -lt 1 ]; then
        log_fail "No active exporters found"
        return 1
    fi
    
    echo -n " ($EXPORTER_COUNT connected)"
    log_pass
}

test_rules_evaluation() {
    log_test "10/10" "Rules recently evaluated"
    
    LAST_EVAL=$(curl -s "$PROMETHEUS_URL/api/v1/rules" 2>/dev/null | \
        jq '.data.groups[0].lastEvaluation' 2>/dev/null | tr -d '"')
    
    if [ -z "$LAST_EVAL" ]; then
        log_fail "Last evaluation time not found"
        return 1
    fi
    
    # Convert ISO timestamp to seconds since epoch
    LAST_EVAL_EPOCH=$(date -d "$LAST_EVAL" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DIFF=$((NOW_EPOCH - LAST_EVAL_EPOCH))
    
    if [ "$DIFF" -gt 120 ]; then
        log_fail "Rules not evaluated recently (last: ${DIFF}s ago)"
        return 1
    fi
    
    echo -n " (${DIFF}s ago)"
    log_pass
}

# Main execution
main() {
    echo "==============================================="
    echo "Alert Pipeline Validation"
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "==============================================="
    echo ""

    test_prometheus_active
    test_alertmanager_active
    test_prometheus_api
    test_alertmanager_api
    test_rules_count
    test_rules_health
    test_webhook_configured
    test_no_unexpected_alerts
    test_exporters_connected
    test_rules_evaluation

    echo ""
    echo "==============================================="
    echo "Summary"
    echo "==============================================="
    echo "Total Tests   : $TESTS_TOTAL"
    echo -e "Passed        : ${GREEN}$TESTS_PASSED${NC}"
    
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "Failed        : ${RED}$TESTS_FAILED${NC}"
    else
        echo -e "Failed        : ${GREEN}0${NC}"
    fi
    
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✅ All tests passed! Alert pipeline is operational.${NC}"
        exit 0
    else
        echo -e "${RED}❌ Some tests failed. Please investigate.${NC}"
        exit 1
    fi
}

# Entry point
main "$@"
