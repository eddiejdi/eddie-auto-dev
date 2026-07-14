#!/usr/bin/env bash
# Permanent Cloudflare Tunnel WAN bypass — survives ProtonVPN policy routing rebuilds.
#
# Layers:
#   1) UID policy rule: cloudflared user (_rpa4all) → table cloudflared-wan (206)
#   2) Subnet routes: 198.41.x + 162.158.x em main (fallback VPN-down) + cloudflared-wan
#   3) DNS resolvers 1.1.1.1/1.0.0.1 via WAN in cloudflared-wan table
#
# NUNCA injetar as faixas Cloudflare na tabela 205 (ProtonVPN): ela roteia a
# LAN inteira, e não há MASQUERADE LAN→eth-wan — clientes da LAN acessando
# qualquer site atrás da Cloudflare (162.158.0.0/15) perdiam a conexão
# (incidente 2026-07-14: downloads grandes quebrando). O bypass do cloudflared
# é garantido apenas pela regra de UID → tabela 206.
#
# Install:
#   sudo cp deploy/vpn/cloudflared-vpn-routes.sh /usr/local/sbin/
#   sudo systemctl enable --now cloudflared-vpn-routes.service cloudflared-vpn-routes.timer
set -euo pipefail

WAN_IF="${WAN_IF:-$(ip route show default | awk '/^default/ {print $5; exit}')}"
WAN_GW="${WAN_GW:-$(ip route show default dev "$WAN_IF" | awk '/^default/ {print $3; exit}')}"
PROTONVPN_TABLE="${PROTONVPN_TABLE:-205}"
CF_TABLE="${CF_TABLE:-206}"
CF_TABLE_NAME="${CF_TABLE_NAME:-cloudflared-wan}"
CF_USER="${CF_USER:-_rpa4all}"
CF_RULE_PRIO="${CF_RULE_PRIO:-90}"

CF_NETS=(
  "198.41.192.0/24"
  "198.41.200.0/24"
  "162.158.0.0/15"
)
CF_DNS=(
  "1.1.1.1"
  "1.0.0.1"
)

log() { logger -t cloudflared-vpn-routes "$*"; echo "$*"; }

if [[ -z "${WAN_IF}" || -z "${WAN_GW}" ]]; then
  log "Nao foi possivel determinar a rota WAN ativa"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Execute como root" >&2
  exit 1
fi

ensure_rt_table() {
  if ! grep -qE "^${CF_TABLE}[[:space:]]+${CF_TABLE_NAME}$" /etc/iproute2/rt_tables 2>/dev/null; then
    echo "${CF_TABLE} ${CF_TABLE_NAME}" >> /etc/iproute2/rt_tables
    log "rt_table ${CF_TABLE} ${CF_TABLE_NAME} registrada"
  fi
}

ensure_uid_rule() {
  local uid uidrange

  if ! id "$CF_USER" &>/dev/null; then
    log "WARN: usuario ${CF_USER} ausente — skip regra UID"
    return 0
  fi

  uid="$(id -u "$CF_USER")"
  uidrange="${uid}-${uid}"

  if ! ip rule show | grep -qE "^${CF_RULE_PRIO}:.*uidrange ${uidrange}.*lookup ${CF_TABLE_NAME}"; then
    while ip rule show | grep -qE "^${CF_RULE_PRIO}:"; do
      ip rule del pref "$CF_RULE_PRIO" 2>/dev/null || break
    done
    ip rule add pref "$CF_RULE_PRIO" uidrange "$uidrange" lookup "$CF_TABLE_NAME"
    log "policy rule ${CF_RULE_PRIO}: uidrange ${uidrange} → table ${CF_TABLE_NAME}"
  fi
}

ensure_cf_table_routes() {
  ip route replace table "$CF_TABLE" default via "$WAN_GW" dev "$WAN_IF"
  ip route replace table "$CF_TABLE" "$WAN_GW" dev "$WAN_IF" scope link

  for dns in "${CF_DNS[@]}"; do
    ip route replace table "$CF_TABLE" "$dns" via "$WAN_GW" dev "$WAN_IF"
  done
}

ensure_subnet_routes() {
  for net in "${CF_NETS[@]}"; do
    ip route replace "$net" via "$WAN_GW" dev "$WAN_IF" table main
    ip route replace "$net" via "$WAN_GW" dev "$WAN_IF" table "$CF_TABLE"
    # remove entradas legadas da tabela 205 (quebravam LAN→Cloudflare)
    ip route del "$net" table "$PROTONVPN_TABLE" 2>/dev/null || true
  done
}

verify_routes() {
  local sample_ip="198.41.200.53" uid_path

  # A rota global (root/LAN) para edges Cloudflare DEVE seguir via protonvpn;
  # só o UID do cloudflared precisa sair pela WAN (regra 90 → tabela 206).
  if id "$CF_USER" &>/dev/null; then
    uid_path="$(sudo -u "$CF_USER" ip route get "$sample_ip" 2>/dev/null || true)"
    if [[ "$uid_path" != *"dev ${WAN_IF}"* ]]; then
      log "VERIFY FAIL: rota UID ${CF_USER} para ${sample_ip}: ${uid_path}"
      return 1
    fi
  fi

  return 0
}

ensure_rt_table
ensure_uid_rule
ensure_cf_table_routes
ensure_subnet_routes
ip route flush cache

if verify_routes; then
  log "OK: Cloudflare via ${WAN_GW} dev ${WAN_IF} (UID table ${CF_TABLE} + main; tabela ${PROTONVPN_TABLE} limpa)"
else
  log "WARN: rotas aplicadas mas verificacao falhou"
  exit 1
fi