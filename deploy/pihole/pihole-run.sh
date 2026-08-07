#!/usr/bin/env bash
# Ensure the Pi-hole container is running with the anti-drift contract:
#   - network_mode=host
#   - Web UI on :8053 only (nginx owns :80/:443)
#   - Named volumes pihole_config + pihole_dnsmasq (live gravity/config on storj)
#
# Install on host: /usr/local/sbin/pihole-run.sh (called by systemd pihole.service)
# Do NOT "docker start" a drifted container and exit — that reintroduced :80/:443.
set -euo pipefail

NAME="${PIHOLE_NAME:-pihole}"
IMAGE="${PIHOLE_IMAGE:-pihole/pihole:latest}"
WEB_PORT="${FTLCONF_webserver_port:-8053}"
VOL_CONFIG="${PIHOLE_CONFIG_VOLUME:-pihole_config}"
VOL_DNSMASQ="${PIHOLE_DNSMASQ_VOLUME:-pihole_dnsmasq}"
# Optional host file for WEBPASSWORD / overrides (never commit secrets).
ENV_FILE="${PIHOLE_ENV_FILE:-/etc/pihole/container.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
fi

WEB_PORT="${FTLCONF_webserver_port:-${WEB_PORT}}"

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -qx "${NAME}"
}

env_web_port() {
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${NAME}" 2>/dev/null \
    | sed -n 's/^FTLCONF_webserver_port=//p' | tail -n1
}

uses_named_volume() {
  local vol="$1" dest="$2"
  docker inspect -f '{{range .Mounts}}{{println .Type " " .Name " " .Destination}}{{end}}' "${NAME}" 2>/dev/null \
    | awk -v v="${vol}" -v d="${dest}" '$1=="volume" && $2==v && $3==d {found=1} END{exit !found}'
}

needs_recreate() {
  if ! container_exists; then
    log "no container ${NAME} — will create"
    return 0
  fi
  local port
  port="$(env_web_port)"
  if [[ "${port}" != "${WEB_PORT}" ]]; then
    log "web port drift: FTLCONF_webserver_port='${port:-<empty>}' want='${WEB_PORT}' — recreate"
    return 0
  fi
  if ! uses_named_volume "${VOL_CONFIG}" "/etc/pihole"; then
    log "volume drift: want ${VOL_CONFIG}:/etc/pihole — recreate"
    return 0
  fi
  if ! uses_named_volume "${VOL_DNSMASQ}" "/etc/dnsmasq.d"; then
    log "volume drift: want ${VOL_DNSMASQ}:/etc/dnsmasq.d — recreate"
    return 0
  fi
  return 1
}

create_container() {
  log "creating ${NAME} image=${IMAGE} web=${WEB_PORT} vols=${VOL_CONFIG},${VOL_DNSMASQ}"
  # WEBPASSWORD may be empty (matches current production); set via ENV_FILE if needed.
  docker run -d \
    --name "${NAME}" \
    --network host \
    --restart unless-stopped \
    --cap-add NET_ADMIN \
    -e TZ="${TZ:-America/Sao_Paulo}" \
    -e "WEBPASSWORD=${WEBPASSWORD:-}" \
    -e FTLCONF_dns_listeningMode="${FTLCONF_dns_listeningMode:-single}" \
    -e FTLCONF_dns_interface="${FTLCONF_dns_interface:-eth-onboard}" \
    -e "FTLCONF_dns_upstreams=${FTLCONF_dns_upstreams:-1.1.1.1;1.0.0.1;8.8.8.8;8.8.4.4}" \
    -e "FTLCONF_webserver_port=${WEB_PORT}" \
    -e FTLCONF_dhcp_active="${FTLCONF_dhcp_active:-false}" \
    -e PIHOLE_DOMAIN="${PIHOLE_DOMAIN:-local}" \
    -e FTL_CMD="${FTL_CMD:-no-daemon}" \
    -v "${VOL_CONFIG}:/etc/pihole" \
    -v "${VOL_DNSMASQ}:/etc/dnsmasq.d" \
    "${IMAGE}" >/dev/null
}

if needs_recreate; then
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
  create_container
else
  log "contract ok — docker start ${NAME}"
  docker start "${NAME}" >/dev/null || true
fi

# Quick post-check (best-effort)
sleep 2
if docker ps --format '{{.Names}}' | grep -qx "${NAME}"; then
  log "running; expect admin UI on :${WEB_PORT} (nginx should own :80/:443)"
else
  log "ERROR: ${NAME} not running"
  exit 1
fi
