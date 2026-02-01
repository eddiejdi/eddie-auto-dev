#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 user@host [user@host ...]" >&2
  exit 1
fi

for host in "$@"; do
  echo "Restarting specialized-agents-api on $host"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" 'sudo systemctl restart specialized-agents-api && echo "restarted" || echo "failed"'
done
