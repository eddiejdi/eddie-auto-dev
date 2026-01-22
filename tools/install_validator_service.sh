#!/usr/bin/env bash
# Installs the auto-validate service into the current user's systemd --user units
set -euo pipefail
SERVICE_SRC="$(pwd)/deploy/auto_validate.service"
USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_DIR"
cp "$SERVICE_SRC" "$USER_DIR/auto_validate.service"
echo "installed $SERVICE_SRC -> $USER_DIR/auto_validate.service"
echo "Reloading systemd --user daemon..."
systemctl --user daemon-reload
echo "Enabling and starting auto_validate.service (systemd --user)"
systemctl --user enable --now auto_validate.service
echo "Status:"; systemctl --user status --no-pager auto_validate.service || true
