#!/usr/bin/env bash
# Upload OpenAPI and draw.io to Confluence and attach to a page.
# Requires: CONFLUENCE_BASE, CONFLUENCE_USER, CONFLUENCE_TOKEN, CONFLUENCE_SPACE, CONFLUENCE_TITLE

set -euo pipefail

BASE=${CONFLUENCE_BASE:-}
USER=${CONFLUENCE_USER:-}
TOKEN=${CONFLUENCE_TOKEN:-}
SPACE=${CONFLUENCE_SPACE:-}
TITLE=${CONFLUENCE_TITLE:-"API Documentation"}

if [ -z "$BASE" ] || [ -z "$USER" ] || [ -z "$TOKEN" ] || [ -z "$SPACE" ]; then
  echo "Set CONFLUENCE_BASE, CONFLUENCE_USER, CONFLUENCE_TOKEN, CONFLUENCE_SPACE" >&2
  exit 2
fi

ROOT=$(dirname "$(dirname "$0")")
OPENAPI=$ROOT/docs/openapi.generated.yaml
DRAWIO=$ROOT/docs/api.drawio

if [ ! -f "$OPENAPI" ]; then
  echo "Generate OpenAPI first: scripts/generate_swagger.py" >&2
  exit 2
fi

API="$BASE/rest/api/content"

# find page
page=$(curl -sS -u "$USER:$TOKEN" "$API?spaceKey=$SPACE&title=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$TITLE")" | jq -r '.results[0].id // empty')
if [ -z "$page" ]; then
  echo "Creating Confluence page: $TITLE"
  body=$(jq -n --arg t "$TITLE" --arg s "$SPACE" '{type:"page",title:$t,space:{key:$s},body:{storage:{value:"<p>API documentation</p>",representation:"storage"}}}')
  page=$(curl -sS -u "$USER:$TOKEN" -H 'Content-Type: application/json' -d "$body" "$API" | jq -r '.id')
  echo "Created page id $page"
fi

echo "Attaching $OPENAPI and $DRAWIO to page $page"
curl -sS -u "$USER:$TOKEN" -X POST -H "X-Atlassian-Token: no-check" -F file=@"$OPENAPI" "$API/$page/child/attachment"
curl -sS -u "$USER:$TOKEN" -X POST -H "X-Atlassian-Token: no-check" -F file=@"$DRAWIO" "$API/$page/child/attachment"

echo "Done. Update page body to embed attachments manually or via Confluence editor."
