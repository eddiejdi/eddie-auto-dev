#!/usr/bin/env bash
# Helper script: deploy minimal app to Fly (free/minimal settings)
# Edit APP, ORG and REGION as needed.

set -euo pipefail

CLOUDFLARE=false
SSH_HOST=
AUTO_APPLY=${AUTO_APPLY:-0}

usage() {
  cat <<EOF
Usage: $0 [--cloudflare] [--ssh-host HOST] [APP] [ORG] [REGION]

Options:
  --cloudflare      Prepare migration instructions to use Cloudflare Tunnel instead of Fly Machines
  --ssh-host HOST   (optional) Hostname to suggest copy of helper scripts (no remote execution by default)
  APP               Fly app name (default: specialized-agents)
  ORG               Fly organization (optional)
  REGION            Fly region (default: ams)

Set AUTO_APPLY=1 in the environment to allow automatic scp to --ssh-host (use with caution).
EOF
}

# parse flags
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --cloudflare)
      CLOUDFLARE=true; shift;;
    --ssh-host)
      SSH_HOST="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      break;;
  esac
done

APP=${1:-specialized-agents}
ORG=${2:-}
REGION=${3:-ams}

if [ "$CLOUDFLARE" = true ]; then
  echo "Preparing Cloudflare Tunnel migration artifacts for app=$APP"
  echo
  echo "Files created in repo: deploy/tunnel/cloudflare/*"
  echo
  echo "Next steps (manual):"
  echo "  1) On a host that will terminate the tunnel (homelab or VM), follow deploy/tunnel/cloudflare/README.md"
  echo "  2) Optionally copy helper script to the host:"
  if [ -n "$SSH_HOST" ]; then
    echo "     scp deploy/tunnel/cloudflare/run_tunnel.sh ${SSH_HOST}:/tmp/run_tunnel.sh"
    if [ "$AUTO_APPLY" = "1" ]; then
      echo "AUTO_APPLY=1 detected — copying helper script to $SSH_HOST"
      scp deploy/tunnel/cloudflare/run_tunnel.sh "${SSH_HOST}:/tmp/run_tunnel.sh"
      echo "Copied. To run interactively on the host: sudo bash /tmp/run_tunnel.sh my-eddie-tunnel eddie.example.com https://heights-treasure-auto-phones.trycloudflare.com"
    else
      echo "(set AUTO_APPLY=1 to enable automatic scp to --ssh-host)"
    fi
  else
    echo "     ssh root@<tunnel-host> and follow README.md; or set --ssh-host to produce scp suggestion"
  fi
  echo
  echo "This mode does NOT run flyctl deploy; it switches you to Cloudflare Tunnel approach to avoid running always-on Fly Machines."
  exit 0
fi

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
