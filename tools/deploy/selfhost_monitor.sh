#!/usr/bin/env bash
# Verifica runners self-hosted e cria uma issue se nenhum estiver disponível
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-eddiejdi/eddie-auto-dev}"
TOKEN="${SELFHOST_MONITOR_TOKEN:-${GITHUB_TOKEN:-}}"

if [ -z "$TOKEN" ]; then
  echo "SELFHOST_MONITOR_TOKEN or GITHUB_TOKEN not set, exiting"
  exit 2
fi

API="https://api.github.com/repos/$REPO/actions/runners"
RESP_TMP=$(mktemp)
HTTP_CODE=$(curl -s -o "$RESP_TMP" -w "%{http_code}" -H "Accept: application/vnd.github+json" -H "Authorization: token $TOKEN" "$API")
RESP=$(cat "$RESP_TMP")
rm -f "$RESP_TMP"

if [ "$HTTP_CODE" != "200" ]; then
  if echo "$RESP" | grep -q "Resource not accessible by integration"; then
    echo "⚠️  GitHub API returned 403: runner listing requires a PAT with admin scope."
    echo "Set the repo secret SELFHOST_MONITOR_TOKEN with a PAT that has 'repo' + 'admin:org' permissions."
    echo "Skipping runner check (non-fatal)."
    exit 0
  fi
  echo "GitHub API error ($HTTP_CODE): $RESP"
  exit 1
fi

FOUND=$(echo "$RESP" | jq -r '.runners[]?.labels[]?.name' | grep -E 'self-hosted|homelab' || true)

if [ -n "$FOUND" ]; then
  echo "Self-hosted runner found:"
  echo "$FOUND"
  exit 0
fi

# Check for an existing open issue with the monitoring title
ISSUE_TITLE="[monitor] self-hosted runner not found"
SEARCH_URL="https://api.github.com/search/issues"
SEARCH_QUERY="$ISSUE_TITLE repo:$REPO state:open"
EXISTING=$(curl -s -G -H "Authorization: token $TOKEN" --data-urlencode "q=$SEARCH_QUERY" "$SEARCH_URL" | jq -r '.total_count')
if [ "$EXISTING" != "0" ]; then
  echo "An open monitoring issue already exists; skipping creation"
  exit 0
fi

# Create an issue to alert
BODY="No self-hosted runner with label 'self-hosted' or 'homelab' was found for repository $REPO.\n\nThis may prevent automated deploys to private homelab hosts.\n\nSteps: install a self-hosted runner or label an existing runner with 'homelab' or 'self-hosted'."
CREATE=$(curl -s -X POST -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$REPO/issues" -d "{\"title\": \"$ISSUE_TITLE\", \"body\": \"$BODY\"}")
if echo "$CREATE" | jq -e '.number' >/dev/null 2>&1; then
  echo "Created issue: $(echo "$CREATE" | jq -r '.html_url')"
  exit 0
else
  echo "Failed to create issue: $CREATE"
  exit 1
fi
