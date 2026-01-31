#!/usr/bin/env bash
# Minimal helper to install a GitHub Actions self-hosted runner on a Linux homelab host.
# Follow GitHub docs for the latest recommended steps: https://docs.github.com/actions/hosting-your-own-runners

set -euo pipefail

REPO="eddiejdi/eddie-auto-dev"
RUNNER_DIR="~/actions-runner"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# You must create a runner registration token in repo settings and place it in env RUNNER_TOKEN
if [ -z "${RUNNER_TOKEN:-}" ]; then
  echo "Please export RUNNER_TOKEN with a registration token from GitHub (Repo > Settings > Actions > Runners > Add runner)."
  exit 1
fi

ARCHIVE="actions-runner-linux-x64-2.308.0.tar.gz"
if [ ! -f "$ARCHIVE" ]; then
  curl -O -L https://github.com/actions/runner/releases/download/v2.308.0/$ARCHIVE
fi

tar xzf $ARCHIVE

./config.sh --url https://github.com/$REPO --token "$RUNNER_TOKEN" --unattended --labels homelab,self-hosted

# To run as service (systemd):
sudo ./svc.sh install
sudo ./svc.sh start

echo "Runner installed and started. Verify in GitHub > Settings > Actions > Runners."

echo "Ensure the runner user has SSH access to the homelab user (or run deploy commands locally)."
