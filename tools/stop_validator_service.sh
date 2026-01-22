#!/usr/bin/env bash
set -euo pipefail
echo "Stopping and disabling auto_validate.service (systemd --user)"
systemctl --user stop auto_validate.service || true
systemctl --user disable auto_validate.service || true
echo "Removing unit file (if exists) from ~/.config/systemd/user/"
rm -f "$HOME/.config/systemd/user/auto_validate.service"
systemctl --user daemon-reload
echo "Done."
