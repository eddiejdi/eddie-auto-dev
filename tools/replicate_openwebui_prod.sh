#!/usr/bin/env bash
set -euo pipefail

# replicate_openwebui_prod.sh
# Helper script to apply the Open WebUI fix to production via flyctl.
# Dry-run by default. Provide --yes to execute.

APP=${FLY_APP_PROD:-}
KEY=${OAUTH_SESSION_TOKEN_ENCRYPTION_KEY:-}
TOKEN=${FLY_API_TOKEN:-}
IMG=${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:main}

usage(){
  cat <<EOF
Usage: $0 [--yes]

Environment variables expected (or set in environment file):
  FLY_API_TOKEN                 - fly.io API token
  FLY_APP_PROD                  - fly app name to operate on
  OAUTH_SESSION_TOKEN_ENCRYPTION_KEY - oauth encryption key to set as secret

Options:
  --yes    Execute (non-dry-run). Without --yes the script prints actions.
EOF
}

DRY_RUN=1
if [ "${1:-}" = "--yes" ]; then
  DRY_RUN=0
fi

if [ -z "$APP" ]; then
  echo "FLY_APP_PROD not set. Set it or export FLY_APP_PROD." >&2
  usage
  exit 2
fi

if [ -z "$TOKEN" ]; then
  echo "FLY_API_TOKEN not set. Set it to authenticate flyctl." >&2
  usage
  exit 2
fi

if [ -z "$KEY" ]; then
  echo "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY not set. Provide a secure key." >&2
  usage
  exit 2
fi

echo "Target app: $APP"
echo "Image: $IMG"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry-run: the following commands would be executed:"
  echo "  flyctl auth login --token <redacted>"
  echo "  flyctl secrets set OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=... --app $APP"
  echo "  flyctl deploy --app $APP --image $IMG"
  echo "Run with --yes to execute for real."
  exit 0
fi

echo "Authenticating with flyctl..."
flyctl auth login --token "$TOKEN"

echo "Setting secret OAUTH_SESSION_TOKEN_ENCRYPTION_KEY..."
flyctl secrets set OAUTH_SESSION_TOKEN_ENCRYPTION_KEY="$KEY" --app "$APP"

echo "Deploying image $IMG to $APP..."
flyctl deploy --app "$APP" --image "$IMG"

echo "Deployment triggered. Check flyctl status and logs for progress."
