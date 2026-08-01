#!/usr/bin/env bash
# Stream filtrado do log do web-agent para a tool `monitor` do Grok.
# Cada linha vira notificação no chat.
#
# Uso (via agent monitor tool):
#   command: /workspace/eddie-auto-dev/tools/hooks/web_agent_log_monitor.sh
#   description: web-agent live log
#   persistent: true
#
# Ou com path custom:
#   WEB_AGENT_LOG=/path/to.log tools/hooks/web_agent_log_monitor.sh
set -uo pipefail

LOG="${WEB_AGENT_LOG:-}"
if [[ -z "$LOG" ]]; then
  for c in \
    "$HOME/.grok/logs/mcp/web-agent.stderr.log" \
    /tmp/web-agent.stderr.log
  do
    if [[ -f "$c" ]]; then LOG="$c"; break; fi
  done
fi

if [[ -z "$LOG" || ! -f "$LOG" ]]; then
  echo "WEB_AGENT_LOG_MISSING path=$HOME/.grok/logs/mcp/web-agent.stderr.log"
  # keep monitor alive a bit so the agent sees the message
  sleep 2
  exit 0
fi

echo "WEB_AGENT_LOG_FOLLOW start file=$LOG"
# -n 5: mostra um pouco de contexto recente ao conectar
# grep line-buffered: crítico para o monitor receber eventos em tempo real
exec tail -n 5 -F "$LOG" 2>/dev/null | grep --line-buffered -E \
  'Passo |ERROR|WARNING|INFO |Telegram|ask_human|STATUS:|BILLING|FAILED|navigate|fill_field|click|signup|login|console\.runpod|OTP|humano'
