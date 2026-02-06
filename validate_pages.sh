#!/bin/bash
# Comprehensive API and Streamlit validation tests

echo "============================================"
echo "  Eddie Auto-Dev - Validation Tests"
echo "============================================"
echo ""

# Test counters
PASS=0
FAIL=0

test_endpoint() {
    local name="$1"
    local url="$2"
    local expected="$3"
    
    result=$(curl -s --max-time 10 "$url" 2>&1)
    if echo "$result" | grep -q "$expected"; then
        echo "✅ PASS: $name"
        ((PASS++))
    else
        echo "❌ FAIL: $name"
        echo "   Expected: $expected"
        echo "   Got: ${result:0:100}..."
        ((FAIL++))
    fi
}

echo "=== API Health Checks ==="
HOMELAB_HOST=${HOMELAB_HOST:-localhost}

test_endpoint "API Health" "http://${HOMELAB_HOST}:8503/health" "healthy"
test_endpoint "API Status" "http://${HOMELAB_HOST}:8503/status" "timestamp"
test_endpoint "Streamlit Health" "http://${HOMELAB_HOST}:8502/_stcore/health" "ok"

echo ""
echo "=== Agent Endpoints ==="
test_endpoint "List Agents" "http://${HOMELAB_HOST}:8503/agents" "available_languages"
test_endpoint "Python Agent Info" "http://${HOMELAB_HOST}:8503/agents/python" "Python Expert"

echo ""
echo "=== Communication Bus ==="
test_endpoint "Comm Messages" "http://${HOMELAB_HOST}:8503/communication/messages" "messages"
test_endpoint "Comm Stats" "http://${HOMELAB_HOST}:8503/communication/stats" "total_messages"

echo ""
echo "=== Docker & RAG ==="
test_endpoint "Docker Containers" "http://${HOMELAB_HOST}:8503/docker/containers" "containers"
test_endpoint "RAG Search" "http://${HOMELAB_HOST}:8503/rag/search" "results"

echo ""
echo "=== Project Endpoints ==="
test_endpoint "Python Projects" "http://${HOMELAB_HOST}:8503/projects/python" "projects"

echo ""
echo "=== Streamlit Pages ==="
# Test Streamlit main page
if curl -s --max-time 10 "http://${HOMELAB_HOST}:8502" | grep -q "Streamlit"; then
    echo "✅ PASS: Streamlit Main Page"
    ((PASS++))
else
    echo "❌ FAIL: Streamlit Main Page"
    ((FAIL++))
fi

echo ""
echo "============================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "============================================"

if [ $FAIL -eq 0 ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "⚠️  Some tests failed. Check output above."
    exit 1
fi
