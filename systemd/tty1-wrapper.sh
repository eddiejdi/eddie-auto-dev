#!/bin/bash
# tty1-wrapper: Grafana Kiosk Dashboard on physical display (Intel onboard)
# Cycles through multiple dashboards with auto-scroll
# Browser: surf (WebKit2GTK) - replaces Chromium snap for lower CPU/RAM usage

AGETTY_BIN="/sbin/agetty"
TERM_NAME="${TERM:-linux}"
RESTART_DELAY=3
FAST_FAIL_LIMIT=5
FAST_FAIL_WINDOW=15
AUTOLOGIN_USER="${KIOSK_AUTOLOGIN_USER:-homelab}"

fast_failures=0

log_msg() {
  logger -t tty1-wrapper "$1"
}

cleanup() {
  log_msg "Cleaning up X and surf processes"
  pkill -x surf 2>/dev/null || true
  pkill -f "openbox" 2>/dev/null || true
}

trap cleanup EXIT

# Wait for Grafana to be available
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://localhost:3002/api/health 2>/dev/null; then
    log_msg "Grafana is ready"
    break
  fi
  log_msg "Waiting for Grafana... ($i/30)"
  sleep 2
done

while true; do
  start_ts=$(date +%s)
  log_msg "Starting Grafana kiosk on tty1 (display :0)"

  XINITRC=$(mktemp /tmp/xinitrc-kiosk.XXXXXX)
  cat > "$XINITRC" <<'XINIT'
#!/bin/bash
export DISPLAY=:0

# Disable screen blanking and DPMS
xset s off
xset -dpms
xset s noblank

# Prefer the physical Intel onboard output. HDMI EDID can appear a few seconds
# after X starts, so retry before falling back to any connected output.
CONNECTED_OUT=""
for _ in $(seq 1 15); do
    CONNECTED_OUT=$(xrandr | awk '/^(HDMI|DP)-[0-9]+ connected/ {print $1; exit}')
    [ -n "$CONNECTED_OUT" ] && break
    sleep 1
done

if [ -z "$CONNECTED_OUT" ]; then
    CONNECTED_OUT=$(xrandr | awk '/ connected/ {print $1; exit}')
fi

if [ -n "$CONNECTED_OUT" ]; then
    xrandr --output "$CONNECTED_OUT" --primary --auto
    logger -t tty1-wrapper "Enabled kiosk output $CONNECTED_OUT"
else
    logger -t tty1-wrapper "No connected kiosk output found by xrandr"
fi

# Hide mouse cursor
unclutter -idle 3 -root &

# Minimal window manager
openbox &
sleep 1

# --- Dashboard rotation config ---
DASHBOARDS=(
    "http://localhost:3002/d/homelab-btop/homelab-system-monitor-btop?kiosk&refresh=30s"
    "http://localhost:3002/d/73dbe362-d884-4205-a6c9-24afbd4b03af/akash-network-provider?orgId=1&from=now-3h&to=now&timezone=browser&refresh=30s&kiosk"
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?orgId=1&from=now-1M%2FM&to=now&timezone=browser&var-coin=BTC-USDT&var-profile=conservative&refresh=30s&kiosk"
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?orgId=1&from=now-1M%2FM&to=now&timezone=browser&var-coin=BTC-USDT&var-profile=aggressive&refresh=30s&kiosk"
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?orgId=1&from=now-1M%2FM&to=now&timezone=browser&var-coin=BTC-USDT&var-profile=shadow&refresh=30s&kiosk"
    "http://localhost:3002/d/trading-daily-report-mcp/f09f938a-trading-daily-report-e28094-ollama-mcp?orgId=1&from=now-7d&to=now&timezone=browser&refresh=1h&kiosk"
    "http://localhost:3002/d/storj-node-monitor/storj-storage-node?orgId=1&from=now-24h&to=now&timezone=browser&refresh=2m&kiosk"
)
SCROLL_STEPS=8        # Page Downs por dashboard
SCROLL_INTERVAL=10     # Segundos entre cada Page Down
LOAD_WAIT=10          # Segundos aguardar carregamento
BOTTOM_PAUSE=10       # Pausa no final antes de trocar
# ---------------------------------

IDX=0

while true; do
    URL="${DASHBOARDS[$IDX]}"
    logger -t kiosk-rotation "Dashboard $((IDX+1))/${#DASHBOARDS[@]}: $URL"

    # Matar instância anterior do surf
    pkill -x surf 2>/dev/null
    sleep 1

    # Iniciar surf em fullscreen (usa wmctrl para maximizar)
    surf -F "$URL" &
    SURF_PID=$!

    # Aguardar carregamento
    sleep $LOAD_WAIT

    # Maximizar janela via wmctrl
    wmctrl -r :ACTIVE: -b add,fullscreen 2>/dev/null || true

    # Auto-scroll para baixo
    for i in $(seq 1 $SCROLL_STEPS); do
        WIN=$(xdotool search --pid $SURF_PID 2>/dev/null | tail -1)
        if [[ -n "$WIN" ]]; then
            xdotool key --clearmodifiers --window "$WIN" Next 2>/dev/null
        else
            xdotool key --clearmodifiers Next 2>/dev/null
        fi
        sleep $SCROLL_INTERVAL
    done

    # Pausa no final
    sleep $BOTTOM_PAUSE

    # Próximo dashboard
    IDX=$(( (IDX + 1) % ${#DASHBOARDS[@]} ))
done
XINIT
  chmod +x "$XINITRC"

  xinit "$XINITRC" -- /usr/bin/Xorg :0 vt1 -keeptty -noreset -nolisten tcp 2>/dev/null
  exit_code=$?
  rm -f "$XINITRC"

  end_ts=$(date +%s)
  runtime=$((end_ts - start_ts))

  if [ "$exit_code" -eq 0 ]; then
    log_msg "Kiosk exited normally after ${runtime}s; switching to getty"
    exec "$AGETTY_BIN" --autologin "$AUTOLOGIN_USER" -o "-p -- \\u" 1200 tty1 linux "$TERM_NAME"
  fi

  log_msg "Kiosk exited abnormally (code=${exit_code}, runtime=${runtime}s); restarting in ${RESTART_DELAY}s"

  if [ "$runtime" -lt "$FAST_FAIL_WINDOW" ]; then
    fast_failures=$((fast_failures + 1))
  else
    fast_failures=0
  fi

  if [ "$fast_failures" -ge "$FAST_FAIL_LIMIT" ]; then
    log_msg "Too many fast failures; falling back to getty"
    exec "$AGETTY_BIN" --autologin "$AUTOLOGIN_USER" -o "-p -- \\u" 1200 tty1 linux "$TERM_NAME"
  fi

  cleanup
  sleep "$RESTART_DELAY"
done
