#!/bin/bash
# Kiosk Dashboard Startup Script
# Runs Chromium in fullscreen mode on display :99

set -e

export DISPLAY=:99
export HOME=/home/kiosk
export XDG_RUNTIME_DIR=/run/user/$(id -u kiosk)

# Ensure display is created
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
sleep 2

# Start window manager
openbox --replace &
WM_PID=$!
sleep 1

# Launch Chromium in kiosk mode
chromium-browser \
    --kiosk \
    --no-first-run \
    --no-default-browser-check \
    --disable-fre \
    --disable-background-networking \
    --disable-breakpad \
    --disable-component-extensions-with-background-pages \
    --disable-default-apps \
    --disable-device-discovery-notifications \
    --disable-plugins \
    --disable-plugins-power-saver \
    --disable-preconnect \
    --disable-sync \
    --disable-translate \
    --metrics-recording-only \
    --no-default-browser-check \
    --no-pings \
    --no-service-autorun \
    --enable-features=NetworkService,NetworkServiceInProcess \
    --touch-events=enabled \
    --enable-blink-features=AutomaticFullscreen \
    http://172.17.0.1:8504

# Cleanup
kill $WM_PID 2>/dev/null || true
kill $XVFB_PID 2>/dev/null || true
