#!/usr/bin/env bash
set -euo pipefail

NAME="workstation-win11l"
IMAGE="dockurr/windows"
WEB_PORT="18400"
RDP_PORT="13391"

if ! /usr/bin/docker container inspect "$NAME" >/dev/null 2>&1; then
  BOOT_ARGS=()

  if [ -f /opt/workstation-win11l/storage/boot.iso ]; then
    BOOT_ARGS=( -v /opt/workstation-win11l/storage/boot.iso:/boot.iso )
  fi

  /usr/bin/docker run -d \
    --name "$NAME" \
    --device /dev/kvm \
    --device /dev/net/tun \
    --cap-add NET_ADMIN \
    -e VERSION="11l" \
    -e RAM_SIZE="8G" \
    -e CPU_CORES="4" \
    -e DISK_SIZE="64G" \
    -e LANGUAGE="English" \
    -e REGION="en-US" \
    -e KEYBOARD="en-US" \
    -e USERNAME="Docker" \
    -e PASSWORD="admin" \
    -p 127.0.0.1:${WEB_PORT}:8006 \
    -p 127.0.0.1:${RDP_PORT}:3389/tcp \
    -p 127.0.0.1:${RDP_PORT}:3389/udp \
    -v /opt/workstation-win11l/storage:/storage \
    -v /opt/workstation-win11l/shared:/shared \
    "${BOOT_ARGS[@]}" \
    --restart no \
    "$IMAGE"
else
  /usr/bin/docker start "$NAME" >/dev/null || true
fi