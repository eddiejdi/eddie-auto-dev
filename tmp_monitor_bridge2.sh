#!/bin/bash
LOG=/home/homelab/eddie-auto-dev/monitor_bridge.log
echo "--- monitor start $(date) ---" >> "$LOG"
# Monitor journal for errors/exceptions and important warnings (use sudo to access journal)
sudo journalctl -u specialized-agents-api.service -f --no-pager | while IFS= read -r line; do
  if echo "$line" | grep -E -i "error|exception|traceback|fail|forbidden|403|timeout|cannot|unhandled" >/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') $line" >> "$LOG"
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S') $line" >> /home/homelab/eddie-auto-dev/monitor_bridge_recent.log
done
