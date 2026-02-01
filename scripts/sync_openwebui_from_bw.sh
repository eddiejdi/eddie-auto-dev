#!/usr/bin/env bash
set -euo pipefail

REPO="eddiejdi/eddie-auto-dev"
ITEM="openwebui/api_key"
SECRET_NAME="OPENWEBUI_API_KEY"
RUN_WORKFLOW=false

usage() {
  cat <<EOF
Usage: $0 [--run-workflow] [--help]

Reads the Open WebUI API key from Bitwarden (item: ${ITEM}) and sets the
repository secret ${SECRET_NAME} in ${REPO} using 'gh'. Optionally triggers
the existing workflow 'write-openwebui-token.yml' which writes the token to
the homelab runner at ~homelab/.openwebui_token.

Prerequisites:
  - Bitwarden CLI: https://bitwarden.com/help/article/cli/
  - GitHub CLI:   https://cli.github.com/
  - You must be logged in to 'bw' and 'gh' and have permissions to set repo secrets.

Options:
  --run-workflow    Trigger the 'write-openwebui-token.yml' workflow after setting secret
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-workflow)
      RUN_WORKFLOW=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

command -v bw >/dev/null 2>&1 || { echo "bw(1) not found. Install Bitwarden CLI and login first." >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "gh(1) not found. Install GitHub CLI and authenticate first." >&2; exit 1; }

# Retrieve token from Bitwarden
echo "Retrieving '${ITEM}' from Bitwarden..."
TMPERR=$(mktemp)
TOKEN=$(bw get password "$ITEM" 2>"$TMPERR" || true)
if [ -z "$TOKEN" ]; then
  echo "Failed to retrieve token from Bitwarden ('$ITEM')." >&2
  echo "See details:" >&2; sed -n '1,200p' "$TMPERR" >&2 || true
  rm -f "$TMPERR"
  exit 1
fi
rm -f "$TMPERR"

# Basic validation
if [ ${#TOKEN} -lt 16 ]; then
  echo "Retrieved token seems too short (${#TOKEN} chars). Aborting." >&2
  exit 1
fi

# Set GitHub secret
echo "Setting repository secret ${SECRET_NAME} in ${REPO}..."
# gh allows setting secret from stdin with --body - (requires gh >= 2.0)
if echo -n "$TOKEN" | gh secret set "$SECRET_NAME" --repo "$REPO" --body -; then
  echo "Secret ${SECRET_NAME} set successfully."
else
  echo "Failed to set secret ${SECRET_NAME}. Ensure you have repo admin permissions and 'gh' is authenticated." >&2
  exit 1
fi

if [ "$RUN_WORKFLOW" = true ]; then
  echo "Triggering workflow 'write-openwebui-token.yml' to write token to homelab..."
  if gh workflow run write-openwebui-token.yml --repo "$REPO"; then
    echo "Workflow dispatched. Verify Actions -> Write OpenWebUI token to homelab in GitHub UI." 
  else
    echo "Failed to dispatch workflow. You may need additional permissions to run workflows." >&2
  fi
fi

echo "Done."
