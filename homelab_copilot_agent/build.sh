#!/usr/bin/env bash
set -euo pipefail

# build.sh [DOCKERFILE] [IMAGE]
# - Prefere `docker buildx` quando disponível
# - Em fallback tenta `DOCKER_BUILDKIT=1 docker build`
# - Último recurso: `docker build` (legacy)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
# Default Dockerfile path and build context match the repository layout used by docker-compose
# Default: Dockerfile in this directory, context = repo root (..)
DOCKERFILE=${1:-Dockerfile}
IMAGE=${2:-homelab-copilot-agent:latest}
CONTEXT=${3:-..}

echo "→ Building $IMAGE using Dockerfile=$DOCKERFILE  context=$CONTEXT"

# Helper to run docker build commands (so we can reuse context correctly)
run_build() {
  shift
  docker "$@" -t "$IMAGE" -f "$DOCKERFILE" "$CONTEXT"
}

if command -v docker >/dev/null 2>&1 && docker buildx version >/dev/null 2>&1; then
  echo "Using docker buildx (BuildKit enabled)"
  docker buildx build --load -t "$IMAGE" -f "$DOCKERFILE" "$CONTEXT"
  exit 0
fi

# Try BuildKit via DOCKER_BUILDKIT env
if DOCKER_BUILDKIT=1 docker build -t "$IMAGE" -f "$DOCKERFILE" "$CONTEXT"; then
  echo "Built with DOCKER_BUILDKIT=1"
  exit 0
fi

# Fallback (legacy builder)
echo "Warning: buildx/BuildKit not available — falling back to legacy builder"
docker build -t "$IMAGE" -f "$DOCKERFILE" "$CONTEXT"
