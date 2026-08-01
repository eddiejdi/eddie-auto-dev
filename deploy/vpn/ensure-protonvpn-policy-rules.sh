#!/bin/bash
# ensure-protonvpn-policy-rules.sh — reaplica só as rules críticas 32764/32765
#
# Motivo: quando ProtonVPN reconecta (ou algum heal mexe em ip rules), as rules
# de policy routing da LAN somem e o tráfego não-IoT cai no DROP do homelab-proxy.
# Este script é leve (sem health-check HTTP) e pode ser chamado de:
#   - iot-vpn-bypass --heal/--restore
#   - cloudflared-vpn-routes.sh
#   - wan-selfheal.sh
#   - dispatcher NM / ExecStartPost
#
# Não chama cloudflared-vpn-routes (evita recursão).
set -euo pipefail

readonly PROTONVPN_FWMARK="${PROTONVPN_FWMARK:-0xca6c}"
readonly PROTONVPN_TABLE="${PROTONVPN_TABLE:-205}"
readonly RULE_PRIO="${POLICY_RULE_PRIORITY:-32764}"
readonly SUPPRESS_PRIO="${MAIN_SUPPRESS_PRIORITY:-32765}"

log() { logger -t ensure-protonvpn-rules "$*"; echo "[ensure-protonvpn-rules] $*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Execute como root" >&2
  exit 1
fi

added=0

if ! ip rule show | grep -Eq "^${RULE_PRIO}:.*lookup ${PROTONVPN_TABLE}( |$)"; then
  # remove residual broken pref if any, then add
  while ip rule show | grep -qE "^${RULE_PRIO}:"; do
    ip rule del pref "$RULE_PRIO" 2>/dev/null || break
  done
  ip rule add not fwmark "$PROTONVPN_FWMARK" table "$PROTONVPN_TABLE" pref "$RULE_PRIO"
  log "rule ${RULE_PRIO} restored: not fwmark ${PROTONVPN_FWMARK} → table ${PROTONVPN_TABLE}"
  added=1
fi

if ! ip rule show | grep -Eq "^${SUPPRESS_PRIO}:.*lookup main suppress_prefixlength 0$"; then
  while ip rule show | grep -qE "^${SUPPRESS_PRIO}:"; do
    ip rule del pref "$SUPPRESS_PRIO" 2>/dev/null || break
  done
  ip rule add lookup main suppress_prefixlength 0 pref "$SUPPRESS_PRIO"
  log "rule ${SUPPRESS_PRIO} restored: lookup main suppress_prefixlength 0"
  added=1
fi

if [[ "$added" -eq 1 ]]; then
  ip route flush cache 2>/dev/null || true
  log "policy rules restored + route cache flushed"
else
  log "policy rules OK (no change)"
fi

exit 0
