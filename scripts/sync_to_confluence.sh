#!/usr/bin/env bash
set -euo pipefail

# Simple Confluence sync helper
# Requires: CONFLUENCE_BASE_URL, CONFLUENCE_USER, CONFLUENCE_API_TOKEN
# Usage: ./sync_to_confluence.sh <space_key> <title> <file.md>

SPACE=${1:-}
TITLE=${2:-}
FILE=${3:-}

if [ -z "$SPACE" ] || [ -z "$TITLE" ] || [ -z "$FILE" ]; then
  echo "usage: $0 <space_key> <title> <file.md>" >&2
  exit 2
fi

if [ -z "${CONFLUENCE_BASE_URL:-}" ] || [ -z "${CONFLUENCE_USER:-}" ] || [ -z "${CONFLUENCE_API_TOKEN:-}" ]; then
  echo "Please set CONFLUENCE_BASE_URL, CONFLUENCE_USER and CONFLUENCE_API_TOKEN" >&2
  exit 2
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "Warning: 'pandoc' not found. Install pandoc to convert markdown to Confluence storage format." >&2
fi

HTML=$(pandoc --from=markdown --to=html "$FILE" 2>/dev/null || sed 's/.*/&/' "$FILE")

API_URL="$CONFLUENCE_BASE_URL/rest/api/content"

cat > /tmp/confluence_payload.json <<JSON
{
  "type": "page",
  "title": "$TITLE",
  "space": { "key": "$SPACE" },
  "body": { "storage": { "value": "$(echo "$HTML" | sed 's/"/\\"/g')", "representation": "storage" } }
}
JSON

curl -sS -u "$CONFLUENCE_USER:$CONFLUENCE_API_TOKEN" -H 'Content-Type: application/json' -d @/tmp/confluence_payload.json "$API_URL"

echo "Done (response printed above)."
