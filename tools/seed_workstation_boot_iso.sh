#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_ISO="${LOCAL_ISO:-$ROOT_DIR/tmp/win11x64-enterprise-ltsc-eval.iso}"
ISO_URL="${ISO_URL:-https://software-static.download.prss.microsoft.com/dbazure/888969d5-f34g-4e03-ac9d-1f9786c66749/26100.1.240331-1435.ge_release_CLIENT_IOT_LTSC_EVAL_x64FRE_en-us.iso}"
REMOTE_HOST="${REMOTE_HOST:-homelab@192.168.15.2}"
REMOTE_KEY="${REMOTE_KEY:-$HOME/.ssh/homelab_key}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/workstation-boot.iso}"
REMOTE_BOOT_ISO="${REMOTE_BOOT_ISO:-/opt/workstation-win11l/storage/boot.iso}"

mkdir -p "$(dirname "$LOCAL_ISO")"

wget -c "$ISO_URL" -O "$LOCAL_ISO"

scp -i "$REMOTE_KEY" -o BatchMode=yes -o StrictHostKeyChecking=no "$LOCAL_ISO" "$REMOTE_HOST:$REMOTE_TMP"

ssh -i "$REMOTE_KEY" -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$REMOTE_HOST" '
set -euo pipefail
sudo mv "'$REMOTE_TMP'" "'$REMOTE_BOOT_ISO'"
sudo chown homelab:homelab "'$REMOTE_BOOT_ISO'"
rm -f /opt/workstation-win11l/storage/tmp/win11x64-enterprise-ltsc-eval.iso
docker stop workstation-win11l >/dev/null 2>&1 || true
curl -fsS http://127.0.0.1:8400/ >/dev/null
docker inspect workstation-win11l --format "status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}}"
'