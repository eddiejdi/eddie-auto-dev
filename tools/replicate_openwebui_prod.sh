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
FLY_MINIMAL=0
USE_CLOUDFLARE=0
#!/usr/bin/env bash
# Fly.io is no longer used. This helper has been disabled to avoid any
# accidental interactions with flyctl or Fly apps. Restore from VCS
# history if you need to re-enable deployment automation.

echo "Fly.io removed — replicate_openwebui_prod.sh is disabled."
exit 0
fi

echo "Setting secret OAUTH_SESSION_TOKEN_ENCRYPTION_KEY..."
flyctl secrets set OAUTH_SESSION_TOKEN_ENCRYPTION_KEY="$KEY" --app "$APP"

echo "Deploying image $IMG to $APP..."
flyctl deploy --app "$APP" --image "$IMG"

# Apply minimal sizing if requested
if [ "$FLY_MINIMAL" = "1" ]; then
  echo "Applying minimal VM size and instance count (shared-cpu-1x, count 1)"
  flyctl scale vm shared-cpu-1x --app "$APP" || true
  flyctl scale count 1 --app "$APP" || true
fi

echo "Deployment triggered. Check flyctl status and logs for progress."
