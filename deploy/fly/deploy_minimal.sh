#!/usr/bin/env bash
# Helper script: deploy minimal app to Fly (free/minimal settings)
# Edit APP, ORG and REGION as needed.

set -euo pipefail

APP=${1:-specialized-agents}
ORG=${2:-}
REGION=${3:-ams}

echo "Deploying $APP to Fly (region=$REGION) with minimal settings"

if [ -n "$ORG" ]; then
  flyctl apps create "$APP" --org "$ORG" --region "$REGION" || true
else
  flyctl apps create "$APP" --region "$REGION" || true
fi

echo "Deploying current directory to Fly (app=$APP)"
flyctl deploy --app "$APP"

echo "Scaling VM to smallest shared size and 1 instance"
flyctl scale vm shared-cpu-1x --app "$APP"
flyctl scale count 1 --app "$APP"

echo "Done. Verify with: flyctl status --app $APP && flyctl ips list --app $APP"
