#!/bin/bash
# Complete validation tests for Eddie Auto-Dev

echo "============================================"
echo "  Eddie Auto-Dev - Complete Validation"
echo "============================================"
echo ""

PASS=0
FAIL=0

check_result() {
    if [ $? -eq 0 ]; then
        echo "✅ PASS: $1"
        ((PASS++))
    else
        echo "❌ FAIL: $1"
        ((FAIL++))
    fi
}

echo "=== 1. API Health Checks ==="

# Health endpoint
curl -s --max-time 10 http://192.168.15.2:8503/health | grep -q "healthy"
check_result "API Health"

# Status endpoint  
curl -s --max-time 10 http://192.168.15.2:8503/status | grep -q "timestamp"
check_result "API Status"

# Streamlit health
curl -s --max-time 10 http://192.168.15.2:8502/_stcore/health | grep -q "ok"
check_result "Streamlit Health"

echo ""
echo "=== 2. Agent Endpoints ==="

# List agents
curl -s --max-time 10 http://192.168.15.2:8503/agents | grep -q "available_languages"
check_result "List Agents"

# Python agent
curl -s --max-time 10 http://192.168.15.2:8503/agents/python | grep -q "Python Expert"
check_result "Python Agent Info"

# Activate agent
curl -s --max-time 30 -X POST http://192.168.15.2:8503/agents/javascript/activate | grep -q "JavaScript"
check_result "Activate JavaScript Agent"

echo ""
echo "=== 3. Communication Bus ==="

# Get messages
curl -s --max-time 10 http://192.168.15.2:8503/communication/messages | grep -q "messages"
check_result "Communication Messages"

# Get stats
curl -s --max-time 10 http://192.168.15.2:8503/communication/stats | grep -q "total_messages"
check_result "Communication Stats"

# Send test message
curl -s --max-time 10 -X POST "http://192.168.15.2:8503/communication/test?message=validation_test" | grep -q "success"
check_result "Send Test Message"

echo ""
echo "=== 4. Docker Endpoints ==="

# List containers
curl -s --max-time 10 http://192.168.15.2:8503/docker/containers | grep -q "containers"
check_result "Docker Containers"

echo ""
echo "=== 5. RAG Endpoints ==="

# Search RAG (POST method)
curl -s --max-time 30 -X POST http://192.168.15.2:8503/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test","n_results":5}' | grep -q "results"
check_result "RAG Search (POST)"

echo ""
echo "=== 6. Code Generation ==="

# Generate code
result=$(curl -s --max-time 120 -X POST http://192.168.15.2:8503/code/generate \
  -H "Content-Type: application/json" \
  -d '{"language":"python","description":"hello world function","context":""}')

echo "$result" | grep -q "code"
check_result "Code Generation"

echo ""
echo "=== 7. Project Endpoints ==="

# List python projects
curl -s --max-time 10 http://192.168.15.2:8503/projects/python | grep -q "projects"
check_result "List Python Projects"

echo ""
echo "=== 8. Streamlit UI ==="

# Main page
curl -s --max-time 10 http://192.168.15.2:8502 | grep -q "Streamlit"
check_result "Streamlit Main Page"

echo ""
echo "=== 9. Communication Log Validation ==="

# Check if messages were recorded
msg_count=$(curl -s http://192.168.15.2:8503/communication/stats | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_messages',0))")
if [ "$msg_count" -gt 5 ]; then
    echo "✅ PASS: Communication Log Recording ($msg_count messages)"
    ((PASS++))
else
    echo "❌ FAIL: Communication Log Recording (only $msg_count messages)"
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
    echo "⚠️  Some tests failed. Review output above."
    exit 1
fi
