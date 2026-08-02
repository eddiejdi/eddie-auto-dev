#!/bin/bash
# Watchdog: detecta eth0 ausente no namespace do container Storj e corrige automaticamente.
# Causa: reconexões ProtonVPN reiniciam storj-host-shim sem recriar macvlan no container.

CONTAINER=storagenode
SHIM_IF=${STORJ_SHIM_IF:-storj-host0}
LOG_TAG='storj-watchdog'

log() { logger -t "$LOG_TAG" "$1"; echo "$(date -u +%FT%TZ) $1"; }

# 0. Guard-rail: arp_ignore=2 em storj-host0 (interface /32) faz o host parar
#    de responder ARP para o container mesmo com a entrada PERMANENT correta
#    (ver systemd/99-storj-host0.sysctl.conf). Sem auditd rastreando quem edita
#    sysctl, uma reintroducao manual passa despercebida ate o proximo outage —
#    corrige e loga aqui a cada ciclo do watchdog.
ARP_IGNORE_PATH="/proc/sys/net/ipv4/conf/${SHIM_IF}/arp_ignore"
if [ -e "$ARP_IGNORE_PATH" ]; then
  CUR_ARP_IGNORE=$(cat "$ARP_IGNORE_PATH" 2>/dev/null)
  if [ -n "$CUR_ARP_IGNORE" ] && [ "$CUR_ARP_IGNORE" != '0' ]; then
    log "FIX: net.ipv4.conf.${SHIM_IF}.arp_ignore=${CUR_ARP_IGNORE} (esperado 0) — corrigindo"
    sysctl -w "net.ipv4.conf.${SHIM_IF}.arp_ignore=0" >/dev/null 2>&1
    if [ -f /etc/sysctl.d/99-storj-host0.conf ] && ! grep -q "^net.ipv4.conf.${SHIM_IF}.arp_ignore = 0" /etc/sysctl.d/99-storj-host0.conf; then
      log "WARN: /etc/sysctl.d/99-storj-host0.conf nao reflete arp_ignore=0 — verificar reintroducao manual"
    fi
  fi
fi

# 1. Container rodando?
CPID=$(docker inspect "$CONTAINER" --format '{{.State.Pid}}' 2>/dev/null)
if [ -z "$CPID" ] || [ "$CPID" = '0' ]; then
  log 'SKIP: container nao esta rodando'
  exit 0
fi

# 2. eth0 presente no namespace?
if nsenter -t "$CPID" -n ip link show eth0 >/dev/null 2>&1; then
  if nsenter -t "$CPID" -n ip addr show eth0 2>/dev/null | grep -q '192.168.15.250'; then
    log 'OK: eth0 presente com IP correto'
    exit 0
  fi
  log 'WARN: eth0 presente mas sem IP 192.168.15.250'
fi

log 'FIX: eth0 ausente ou sem IP no namespace — reiniciando container'
docker restart "$CONTAINER"
sleep 8

# 3. Recriar shim e ip rules
log 'Reiniciando storj-host-shim...'
systemctl restart storj-host-shim.service
sleep 2

# 4. Validar resultado
NEW_CPID=$(docker inspect "$CONTAINER" --format '{{.State.Pid}}' 2>/dev/null)
if nsenter -t "$NEW_CPID" -n ip addr show eth0 2>/dev/null | grep -q '192.168.15.250'; then
  log 'RECOVERED: eth0 restaurado com IP 192.168.15.250'
else
  log 'ERROR: falha ao restaurar eth0 — intervencao manual necessaria'
  exit 1
fi
