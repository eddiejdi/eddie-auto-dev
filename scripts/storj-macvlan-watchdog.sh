#!/bin/bash
# Watchdog: detecta eth0 ausente no namespace do container Storj e corrige automaticamente.
# Causa: reconexões ProtonVPN reiniciam storj-host-shim sem recriar macvlan no container.

CONTAINER=storagenode
LOG_TAG='storj-watchdog'

log() { logger -t "$LOG_TAG" "$1"; echo "$(date -u +%FT%TZ) $1"; }

WAN_IFACE="${WAN_IFACE:-eth-wan}"
EXPECTED_IP="${EXPECTED_IP:-192.168.15.250}"

# 0. Parent da rede Docker alinhado com a iface viva (eth-wan).
# Sem isso, docker start falha com "parent interface ... was not found"
# e o self-heal só faz restart em loop (incidente 2026-08-14).
PARENT=$(docker network inspect storj_macvlan -f '{{index .Options "parent"}}' 2>/dev/null || true)
if [ "$PARENT" != "$WAN_IFACE" ]; then
  if ! ip link show "$WAN_IFACE" >/dev/null 2>&1; then
    log "ERROR: $WAN_IFACE ausente — nao posso recriar storj_macvlan (parent atual='$PARENT')"
    exit 1
  fi
  CPID_NOW=$(docker inspect "$CONTAINER" --format '{{.State.Pid}}' 2>/dev/null || echo 0)
  if [ -n "$CPID_NOW" ] && [ "$CPID_NOW" != '0' ]; then
    log "WARN: storj_macvlan parent='$PARENT' (esperado $WAN_IFACE) mas container esta UP — nao recrio a quente"
  else
    log "FIX: storj_macvlan parent='$PARENT' -> $WAN_IFACE"
    docker network disconnect -f storj_macvlan "$CONTAINER" 2>/dev/null || true
    docker network rm storj_macvlan 2>/dev/null || true
    docker network create -d macvlan --subnet=192.168.15.0/24 --gateway=192.168.15.1 \
      --ip-range="${EXPECTED_IP}/32" -o "parent=${WAN_IFACE}" storj_macvlan
    docker network connect --ip "$EXPECTED_IP" storj_macvlan "$CONTAINER" 2>/dev/null || true
    docker start "$CONTAINER" 2>/dev/null || true
    sleep 5
  fi
fi

# 1. Container rodando?
CPID=$(docker inspect "$CONTAINER" --format '{{.State.Pid}}' 2>/dev/null)
if [ -z "$CPID" ] || [ "$CPID" = '0' ]; then
  ERR=$(docker inspect "$CONTAINER" --format '{{.State.Error}}' 2>/dev/null || true)
  log "SKIP: container nao esta rodando (${ERR:-sem erro})"
  exit 0
fi

# 2. eth0 presente no namespace?
if nsenter -t "$CPID" -n ip link show eth0 >/dev/null 2>&1; then
  if nsenter -t "$CPID" -n ip addr show eth0 2>/dev/null | grep -q "$EXPECTED_IP"; then
    log 'OK: eth0 presente com IP correto'
    exit 0
  fi
  log "WARN: eth0 presente mas sem IP $EXPECTED_IP"
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
if nsenter -t "$NEW_CPID" -n ip addr show eth0 2>/dev/null | grep -q "$EXPECTED_IP"; then
  log "RECOVERED: eth0 restaurado com IP $EXPECTED_IP"
else
  log 'ERROR: falha ao restaurar eth0 — intervencao manual necessaria'
  exit 1
fi
