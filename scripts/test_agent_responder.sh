#!/usr/bin/env bash
set -euo pipefail
API=${API_URL:-http://127.0.0.1:8503}

echo "Activating python agent..."
curl -sS -X POST "$API/agents/python/activate" | jq .

# give agent a moment to register before publishing the broadcast
sleep 1

echo "Starting responder (if needed) and publishing coordinator broadcast via /communication/test..."
curl -sS -X POST "$API/communication/test" -H 'Content-Type: application/json' -d '{"message":"please_respond", "start_responder": true}' | jq .

# give responder a moment to reply
sleep 2

echo "Fetching recent messages (limit=50)..."
curl -sS "$API/communication/messages?limit=50" | jq '.messages[] | {type:.type, source:.source, content:(.content|split("\n")[0])}'
