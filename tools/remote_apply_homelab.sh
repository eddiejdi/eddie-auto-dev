#!/usr/bin/env bash
set -euo pipefail

# remote_apply_homelab.sh
# SSH wrapper to run apply_homelab_fly_free_policy.sh on the homelab server (192.168.15.2).
# Usage:
#   ./tools/remote_apply_homelab.sh         # dry-run remote
#   ./tools/remote_apply_homelab.sh --apply
# The script will:
#  - SSH to 192.168.15.2 and, if the repository path exists there, execute the
#    apply script from that path. Otherwise it copies the minimal files needed
#    to /tmp/eddie-auto-dev on the remote host and executes from there.

REMOTE=192.168.15.2
REMOTE_USER=${REMOTE_USER:-root}

# Safety: require explicit confirmation that WSL (if used) was restarted.
# User must set WSL_RESTARTED=1 in the environment after closing/reopening WSL
# before this script will perform remote execution. This enforces your rule
# to restart WSL before running commands.
if [[ "${WSL_RESTARTED:-0}" != "1" ]]; then
  echo "Aborting: please restart WSL and set WSL_RESTARTED=1 in your environment before running this script." >&2
  echo "Example: (after restarting) export WSL_RESTARTED=1 && bash tools/remote_apply_homelab.sh --apply" >&2
  exit 2
fi
REPO_LOCAL=$(cd "$(dirname "$0")/.." && pwd)
SCRIPT_REL=tools/apply_homelab_fly_free_policy.sh
SCRIPT_LOCAL="$REPO_LOCAL/$SCRIPT_REL"

if [[ ! -f "$SCRIPT_LOCAL" ]]; then
  echo "Local script not found: $SCRIPT_LOCAL" >&2
  exit 2
fi

DRY_RUN=1
if [[ ${1:-} = "--apply" ]]; then DRY_RUN=0; fi

echo "Connecting to ${REMOTE_USER}@${REMOTE}..."

ssh ${REMOTE_USER}@${REMOTE} bash -c "'set -euo pipefail; if [ -f \"$REPO_LOCAL/$SCRIPT_REL\" ]; then echo Running existing repo script; sudo bash \"$REPO_LOCAL/$SCRIPT_REL\" ${DRY_RUN:+--dry-run}; exit 0; fi; exit 1'" 2>/dev/null || true

# If remote repo path exists, run there. Otherwise copy minimal files.
REMOTE_HAS_REPO=0
if ssh ${REMOTE_USER}@${REMOTE} test -d "$REPO_LOCAL" 2>/dev/null; then
  REMOTE_HAS_REPO=1
fi

if [[ "$REMOTE_HAS_REPO" -eq 1 ]]; then
  echo "Repository exists on remote; executing script there"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    ssh ${REMOTE_USER}@${REMOTE} "sudo bash '$REPO_LOCAL/$SCRIPT_REL'"
  else
    ssh ${REMOTE_USER}@${REMOTE} "sudo bash '$REPO_LOCAL/$SCRIPT_REL' --apply"
  fi
  exit $?
fi

echo "Repository not found on remote; copying minimal files to /tmp/eddie-auto-dev and executing there"
TMP_REMOTE="/tmp/eddie-auto-dev"
FILES=("$SCRIPT_LOCAL" "$REPO_LOCAL/tools/systemd/autonomous_remediator.env.example" "$REPO_LOCAL/tools/simple_vault/secrets/fly_api_token.txt" "$REPO_LOCAL/flyio-tunnel/fly-tunnel.sh" "$REPO_LOCAL/flyio-tunnel/scripts/flyio-tunnel.sh")

# Ensure remote directory exists and copy files into it
ssh ${REMOTE_USER}@${REMOTE} "mkdir -p /tmp/eddie-auto-dev" || true
for f in "${FILES[@]}"; do
  relpath="${f#$REPO_LOCAL/}"
  remote_dir="/tmp/eddie-auto-dev/$(dirname "$relpath")"
  ssh ${REMOTE_USER}@${REMOTE} "mkdir -p \"$remote_dir\"" || true
  scp "$f" ${REMOTE_USER}@${REMOTE}:"$remote_dir/" || true
done

# Execute from the copied repo root so relative paths resolve (tools/apply...)
CMD="cd /tmp/eddie-auto-dev && sudo bash tools/$(basename $SCRIPT_REL)"
if [[ "$DRY_RUN" -eq 0 ]]; then CMD="$CMD --apply"; fi

echo "Executing on remote: $CMD"
ssh ${REMOTE_USER}@${REMOTE} "$CMD"

echo "Remote execution finished"
