#!/usr/bin/env bash
set -euo pipefail
API=${API_URL:-http://127.0.0.1:8503}

echo "Activating python agent..."
curl -sS -X POST "$API/agents/python/activate" | jq .

# give agent a moment to register before publishing the broadcast
sleep 1

echo "Starting responder (if needed) and publishing coordinator broadcast via /communication/test..."

# Try a few times to publish and wait for responses (make test resilient to timing)
SUCCESS=0
for i in 1 2 3 4 5; do
  echo "Attempt $i: publishing..."
  curl -sS -X POST "$API/communication/test" -H 'Content-Type: application/json' -d '{"message":"please_respond", "start_responder": true}' | jq .
  # wait for responder to reply
  sleep 2
  if curl -sS "$API/communication/messages?limit=50" | jq -e '.messages | map(select(.type=="response")) | length > 0' >/dev/null 2>&1; then
    SUCCESS=1
    break
  fi
  echo "No response yet, retrying..."
done

if [ "$SUCCESS" -ne 1 ]; then
  echo "No response messages found after retries" >&2
  curl -sS "$API/communication/messages?limit=50" | jq '.messages[] | {type:.type, source:.source, content:(.content|split("\n")[0])}' >&2 || true
  exit 1
fi

echo "Fetching recent messages (limit=50)..."
curl -sS "$API/communication/messages?limit=50" | jq '.messages[] | {type:.type, source:.source, content:(.content|split("\n")[0])}'
