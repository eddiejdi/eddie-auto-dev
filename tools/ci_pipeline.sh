#!/usr/bin/env bash
set -euo pipefail

# ci_pipeline.sh
# Helper to create a git commit for current workspace changes and optionally
# run the production replication script. Dry-run by default; use --yes to apply.

COMMIT_MSG=""
APPLY=0
DEPLOY_PROD=0

usage(){
  cat <<EOF
Usage: $0 --message "commit message" [--yes] [--deploy-prod]

--message/-m   Commit message to use
--yes          Execute commands (git commit, push, deploy). Without it the
               script prints the actions (dry-run).
--deploy-prod  After pushing, run production replication (requires FLY_API_TOKEN)

Examples:
  $0 -m "Enable autonomous remediator"        # dry-run
  $0 -m "Enable autonomous remediator" --yes  # commit and push
  $0 -m "Enable" --yes --deploy-prod         # commit, push, deploy via flyctl

EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message)
      COMMIT_MSG="$2"; shift 2;;
    --yes)
      APPLY=1; shift;;
    --deploy-prod)
      DEPLOY_PROD=1; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [ -z "$COMMIT_MSG" ]; then
  echo "Missing commit message" >&2; usage; exit 2
fi

echo "Preparing pipeline with commit message: $COMMIT_MSG"

# Show git status and planned commands
echo
echo "---- git status ----"
git status --porcelain
echo "--------------------"

echo
echo "Planned actions:"
echo "  git add -A"
echo "  git commit -m '$COMMIT_MSG'"
echo "  git push origin HEAD"
if [ $DEPLOY_PROD -eq 1 ]; then
  echo "  ./tools/replicate_openwebui_prod.sh --yes  (deploy to prod)"
fi

if [ $APPLY -eq 0 ]; then
  echo "Dry-run mode. Rerun with --yes to apply."; exit 0
fi

echo "Applying git commit and push..."
git add -A
git commit -m "$COMMIT_MSG" || true
git push origin HEAD

if [ $DEPLOY_PROD -eq 1 ]; then
  echo "Triggering production replication..."
  # rely on environment variables (FLY_API_TOKEN, FLY_APP_PROD, OAUTH_SESSION_TOKEN_ENCRYPTION_KEY)
  if [ -z "${FLY_API_TOKEN:-}" ]; then
    echo "FLY_API_TOKEN not set in environment. Aborting deploy." >&2
    exit 3
  fi
  ./tools/replicate_openwebui_prod.sh --yes
fi

echo "Pipeline complete. Verify CI and monitor services." 
