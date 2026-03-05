#!/bin/bash
set -e

# Espera o emulador bootar
adb wait-for-device
sleep 10

# Root e remount system
adb root || true
adb remount || true

# Instala certificado CA do mitmproxy
if [ -f /mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem ]; then
  adb push /mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem /sdcard/
  adb shell 'mount -o remount,rw /system'
  adb shell 'cp /sdcard/mitmproxy-ca-cert.pem /system/etc/security/cacerts/9a5ba575.0'
  adb shell 'chmod 644 /system/etc/security/cacerts/9a5ba575.0'
fi

# Instala APK do Tap Gallery (assume apk já baixado)
if [ -f /apk/tap_gallery.apk ]; then
  adb install -r /apk/tap_gallery.apk
fi

# Configura proxy WiFi (opcional, já setado via env)
# adb shell settings put global http_proxy mitmproxy:8080

# Pronto
