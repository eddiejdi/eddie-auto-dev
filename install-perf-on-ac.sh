#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0"
  exit 2
fi

echo "Updating package lists..."
apt update

echo "Installing helper packages..."
DEBIAN_FRONTEND=noninteractive apt install -y smartmontools zram-tools

echo "Creating helper scripts and units..."

# set-cpu-governor.sh
cat > /usr/local/sbin/set-cpu-governor.sh <<'SH'
#!/bin/bash
GOV=${1:-performance}
for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  echo "$GOV" > "$f" || true
done
SH
chmod +x /usr/local/sbin/set-cpu-governor.sh

# perf-on-ac.sh
cat > /usr/local/sbin/perf-on-ac.sh <<'SH'
#!/bin/bash
set -euo pipefail

# detect AC
AC=0
if [ -r /sys/class/power_supply/AC/online ]; then
  AC=$(cat /sys/class/power_supply/AC/online)
elif command -v upower >/dev/null 2>&1; then
  AC=$(upower -i /org/freedesktop/UPower/devices/line_power_AC 2>/dev/null | awk '/online/ {print $2}')
  [ "$AC" = "yes" ] && AC=1 || AC=0
fi

SYSCTL_DISABLED=/etc/sysctl.d/99-performance.conf.disabled
SYSCTL_ACTIVE=/etc/sysctl.d/99-performance.conf

if [ "$AC" != "1" ]; then
  echo "On battery: reverting AC-only settings if present..."
  [ -f "$SYSCTL_ACTIVE" ] && mv -f "$SYSCTL_ACTIVE" "$SYSCTL_DISABLED" || true
  sysctl --system >/dev/null 2>&1 || true
  systemctl stop zramswap.service >/dev/null 2>&1 || true
  systemctl disable --now set-cpu-governor.service >/dev/null 2>&1 || true
  exit 0
fi

echo "On AC: applying performance profile..."

if [ -f "$SYSCTL_DISABLED" ]; then
  mv -f "$SYSCTL_DISABLED" "$SYSCTL_ACTIVE" || true
else
  cat > "$SYSCTL_ACTIVE" <<'EOF'
# Performance tuning (AC-only)
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF
fi
sysctl --system >/dev/null 2>&1 || true

if [ -w /sys/module/zswap/parameters/enabled ]; then
  echo 1 > /sys/module/zswap/parameters/enabled || true
fi

if systemctl list-unit-files | grep -q zramswap; then
  systemctl enable --now zramswap.service >/dev/null 2>&1 || true
fi

/usr/local/sbin/set-cpu-governor.sh performance >/dev/null 2>&1 || true
systemctl enable --now set-cpu-governor.service >/dev/null 2>&1 || true

systemctl disable --now plocate-updatedb.timer >/dev/null 2>&1 || true

if command -v smartctl >/dev/null 2>&1; then
  smartctl -H /dev/nvme0n1 2>/dev/null || true
fi

echo "Done."
SH
chmod +x /usr/local/sbin/perf-on-ac.sh

# set-cpu-governor.service (only runs when on AC)
cat > /etc/systemd/system/set-cpu-governor.service <<'UNIT'
[Unit]
Description=Set CPU governor at boot (AC only)
ConditionACPower=yes

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/set-cpu-governor.sh performance

[Install]
WantedBy=multi-user.target
UNIT

# perf-on-ac.service
cat > /etc/systemd/system/perf-on-ac.service <<'UNIT'
[Unit]
Description=Apply performance profile when on AC
ConditionACPower=yes

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/perf-on-ac.sh
UNIT

# perf-on-ac.timer
cat > /etc/systemd/system/perf-on-ac.timer <<'UNIT'
[Unit]
Description=Run perf-on-ac.service periodically (only effective while AC)

[Timer]
OnBootSec=1min
OnUnitActiveSec=10min
Persistent=yes

[Install]
WantedBy=timers.target
UNIT

# udev rule to trigger service immediately on power_supply change
cat > /etc/udev/rules.d/99-perf-on-ac.rules <<'RULE'
# Trigger perf-on-ac.service when power supply state changes
ACTION=="change", SUBSYSTEM=="power_supply", RUN+="/bin/systemctl start perf-on-ac.service"
RULE

# leave sysctl disabled file in place initially
cat > /etc/sysctl.d/99-performance.conf.disabled <<'EOF'
# Performance tuning (AC-only)
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF

echo "Reloading systemd and udev rules..."
systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger --subsystem-match=power_supply || true

echo "Enabling timer and running perf-on-ac.sh once now (runs only if AC present)..."
systemctl enable --now perf-on-ac.timer || true
/usr/local/sbin/perf-on-ac.sh || true

echo "Install complete. Reboot recommended if kernel or driver updates were applied."
