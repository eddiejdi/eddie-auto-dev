#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-/home/homelab/docker-compose.grafana.yml}"
CONTAINERS=(prometheus grafana)

log() {
    logger -t ensure-monitoring-containers "$*"
    echo "$*"
}

is_running() {
    local name="$1"
    docker ps \
        --filter "name=^/${name}$" \
        --filter "status=running" \
        --format '{{.Names}}' \
        | grep -qx "$name"
}

start_container() {
    local name="$1"
    if is_running "$name"; then
        log "$name already running"
        return 0
    fi

    if docker start "$name" >/dev/null 2>&1; then
        log "$name started via docker start"
        return 0
    fi

    return 1
}

compose_up() {
    if ! command -v docker-compose >/dev/null 2>&1; then
        log "docker-compose not available for compose fallback"
        return 1
    fi
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log "compose file missing: $COMPOSE_FILE"
        return 1
    fi

    log "running docker-compose fallback for monitoring stack"
    docker-compose -f "$COMPOSE_FILE" up -d "${CONTAINERS[@]}"
}

needs_compose=0
for container in "${CONTAINERS[@]}"; do
    if ! start_container "$container"; then
        log "direct start failed for $container"
        needs_compose=1
    fi
done

if [[ "$needs_compose" -eq 1 ]]; then
    compose_up || true
fi

failed=0
for container in "${CONTAINERS[@]}"; do
    if ! is_running "$container"; then
        log "$container is still down"
        failed=1
    fi
done

exit "$failed"
