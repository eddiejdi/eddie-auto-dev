#!/usr/bin/env bash
# Fly.io is no longer used in this repository.
# This script has been converted to a no-op stub to avoid accidental
# flyctl operations. If you need to re-enable Fly-related automation,
# restore from history or recreate the appropriate tooling.

echo "Fly.io removed — apply_homelab_fly_free_policy.sh is disabled."
exit 0

# apply_homelab_fly_free_policy.sh
# Safe helper to configure the homelab host to use the Fly.io app in a
# free/minimal configuration and to install/copy the autonomous remediator env.
#
# Usage (dry-run):
#   sudo bash tools/apply_homelab_fly_free_policy.sh --dry-run
# To apply changes (writes /etc and restarts services):
#   sudo bash tools/apply_homelab_fly_free_policy.sh --apply

echo "Done (no-op in this trimmed copy)."

DRY_RUN=1
APPLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      DRY_RUN=0; APPLY=1; shift;;
    --install-flyctl)
      INSTALL_FLYCTL=1; shift;;
    --help)
      sed -n '1,120p' "$0"; exit 0;;
    *) echo "Unknown arg: $1"; exit 2;;
  esac
done

REPO=$(cd "$(dirname "$0")/.." && pwd)
# Safety: ensure this script runs on the homelab server (192.168.15.2) by default.
# If you are on a different host, the script will abort to avoid accidental local execution.
LOCAL_ALLOW=0
if [[ "${ALLOW_LOCAL:-0}" = "1" ]]; then LOCAL_ALLOW=1; fi
HOST_OK=0
if ip addr 2>/dev/null | grep -q "192.168.15.2"; then
  HOST_OK=1
fi
if [[ "$LOCAL_ALLOW" -eq 0 && "$HOST_OK" -ne 1 ]]; then
  echo "Refusing to run: this script must be executed on the homelab server 192.168.15.2." >&2
  echo "If you intend to run remotely from this machine, use tools/remote_apply_homelab.sh which will SSH to 192.168.15.2 and run the script there." >&2
  echo "To override locally (not recommended), set ALLOW_LOCAL=1 in the environment." >&2
  exit 2
fi
ENV_EXAMPLE="$REPO/tools/systemd/autonomous_remediator.env.example"
ENV_DEST="/etc/autonomous_remediator.env"
SIMPLE_TOKEN_FILE="$REPO/tools/simple_vault/secrets/fly_api_token.txt"
FLY_TUNNEL_SCRIPT="$REPO/flyio-tunnel/fly-tunnel.sh"
FLY_SCRIPTS="$REPO/flyio-tunnel/scripts/flyio-tunnel.sh"

echo "Dry-run mode: ${DRY_RUN}" >&2

function run_or_echo() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    echo "RUN: $*"
    eval "$*"
  fi
}

# 1) Ensure flyctl exists or show suggestion
FLY_BIN_PATH=""
if [[ -n "${FLY_BIN:-}" ]]; then
  FLY_BIN_PATH="$FLY_BIN"
fi
if [[ -z "$FLY_BIN_PATH" ]]; then
  # check common locations
  for p in /home/homelab/.fly/bin/fly ~/.fly/bin/fly /usr/local/bin/flyctl /usr/bin/flyctl; do
    if [[ -x "$p" ]]; then
      FLY_BIN_PATH="$p"; break
    fi
  done
fi

echo "Detected flyctl path: ${FLY_BIN_PATH:-<none>}"
if [[ -z "$FLY_BIN_PATH" ]]; then
  echo "flyctl not found on this host. To install (interactive), run:" >&2
  echo "  curl -L https://fly.io/install.sh | sh" >&2
  echo "Or re-run this script with --install-flyctl to attempt install (not recommended unattended)." >&2
else
  echo "Will use flyctl: $FLY_BIN_PATH"
fi

# 2) Create /etc/autonomous_remediator.env from example and inject token if present
if [[ ! -f "$ENV_EXAMPLE" ]]; then
  echo "Env example not found: $ENV_EXAMPLE" >&2
else
  echo "Preparing env file: $ENV_DEST"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Would copy $ENV_EXAMPLE -> $ENV_DEST and inject FLY_BIN/FLY_API_TOKEN if available"
  else
    cp "$ENV_EXAMPLE" /tmp/autonomous_remediator.env.tmp
    # inject discovered FLY_BIN
    if [[ -n "$FLY_BIN_PATH" ]]; then
      sed -i "/^FLY_BIN=/d" /tmp/autonomous_remediator.env.tmp || true
      echo "FLY_BIN=$FLY_BIN_PATH" >> /tmp/autonomous_remediator.env.tmp
    fi
    # inject token from simple vault file if present
    if [[ -f "$SIMPLE_TOKEN_FILE" ]]; then
      TOKEN=$(sed -n '1p' "$SIMPLE_TOKEN_FILE" | tr -d '\n')
      sed -i "/^FLY_API_TOKEN=/d" /tmp/autonomous_remediator.env.tmp || true
      echo "FLY_API_TOKEN=$TOKEN" >> /tmp/autonomous_remediator.env.tmp
    fi
    sudo cp /tmp/autonomous_remediator.env.tmp "$ENV_DEST"
    sudo chown root:root "$ENV_DEST"
    sudo chmod 600 "$ENV_DEST"
    rm -f /tmp/autonomous_remediator.env.tmp
    echo "Wrote $ENV_DEST (owner root, mode 600)"
  fi
fi

# 3) If flyctl is present and token/app set, attempt to set app to minimal VM size and single instance
if [[ -n "$FLY_BIN_PATH" ]]; then
  # read env values
  FLY_API_TOKEN_ENV="$(grep -E '^FLY_API_TOKEN=' "$ENV_EXAMPLE" 2>/dev/null || true)"
  # prefer actual file
  if [[ -f "$ENV_DEST" ]]; then
    FLY_APP_NAME=$(grep -E '^FLY_APP_PROD=' "$ENV_DEST" | cut -d'=' -f2- | tr -d '"') || true
    FLY_API_TOKEN_VAL=$(grep -E '^FLY_API_TOKEN=' "$ENV_DEST" | cut -d'=' -f2- | tr -d '"') || true
  else
    FLY_APP_NAME="homelab-tunnel-sparkling-sun-3565"
    FLY_API_TOKEN_VAL=""
  fi

  if [[ -z "$FLY_APP_NAME" ]]; then
    echo "FLY_APP not set in env file; skipping flyctl app commands" >&2
  else
    echo "Target Fly app: $FLY_APP_NAME"
    echo "Planned actions (dry-run prints only):"
    # Prefer using the included helper script if present (handles correct flyctl flags)
    if [[ -f "$REPO/flyio-tunnel/fly-tunnel.sh" ]]; then
      # Prefer token from env file, fallback to simple_vault token file
      if [[ -z "$FLY_API_TOKEN_VAL" && -f "$REPO/tools/simple_vault/secrets/fly_api_token.txt" ]]; then
        FLY_API_TOKEN_VAL=$(sed -n '1p' "$REPO/tools/simple_vault/secrets/fly_api_token.txt" | tr -d '\n') || true
      fi
      if [[ -n "$FLY_API_TOKEN_VAL" ]]; then
        run_or_echo "env FLY_API_TOKEN=\"${FLY_API_TOKEN_VAL}\" FLY_BIN=\"${FLY_BIN_path:-$FLY_BIN_PATH}\" bash \"$REPO/flyio-tunnel/fly-tunnel.sh\" restart"
        run_or_echo "env FLY_API_TOKEN=\"${FLY_API_TOKEN_VAL}\" FLY_BIN=\"${FLY_BIN_path:-$FLY_BIN_PATH}\" bash \"$REPO/flyio-tunnel/fly-tunnel.sh\" test"
      else
        run_or_echo "FLY_BIN=\"${FLY_BIN_PATH}\" bash \"$REPO/flyio-tunnel/fly-tunnel.sh\" restart"
        run_or_echo "FLY_BIN=\"${FLY_BIN_PATH}\" bash \"$REPO/flyio-tunnel/fly-tunnel.sh\" test"
      fi
    else
      # Fallback: restart app using positional app name (avoid -a shorthand)
      run_or_echo "${FLY_BIN_PATH} apps restart $FLY_APP_NAME"
    fi
    # Do not attempt aggressive scaling here; keep minimal manual operations to avoid account issues.
  fi
fi

# 4) Ensure WireGuard service is running and restart remediator/systemd units if applying
echo "Checking WireGuard/systemd services"
run_or_echo "sudo systemctl daemon-reload"
run_or_echo "sudo systemctl restart flyio-wireguard.service || true"
run_or_echo "sudo systemctl restart autonomous_remediator.service || true"
run_or_echo "sudo systemctl restart specialized-agents || true"

# 5) Post-check: test health endpoint(s)
echo "Health checks (curl)
Note: replace URL if different."
run_or_echo "curl -s -o /dev/null -w '%{http_code} %{url_effective}\n' https://homelab-tunnel-sparkling-sun-3565.fly.dev/health || true"

echo "Done. If you ran with --apply, verify logs with: sudo journalctl -u autonomous_remediator.service -f"
