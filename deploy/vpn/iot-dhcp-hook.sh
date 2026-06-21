#!/bin/bash
# /etc/iot-bypass/iot-dhcp-hook.sh
# Chamado pelo dnsmasq via dhcp-script em cada novo lease.
# Classifica o device como IoT e o adiciona automaticamente ao bypass.
#
# Args: $1=add|del|old  $2=MAC  $3=IP  $4=hostname
# Env var: DNSMASQ_TAGS, DNSMASQ_INTERFACE (set by dnsmasq)

set -euo pipefail

ACTION="$1"
MAC="${2:-}"
IP="${3:-}"
HOSTNAME="${4:-}"
LOG="/var/log/iot-bypass-autodetect.log"
NFT_TABLE="ip iot_bypass"
NFT_SET="iot_devices"
PERSIST_FILE="/etc/iot-bypass/iot_ips.txt"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$ACTION] IP=$IP MAC=$MAC HOST=$HOSTNAME → $*" >> "$LOG"
}

is_iot_by_mac() {
  local mac_upper
  mac_upper=$(echo "$MAC" | tr '[:lower:]' '[:upper:]' | tr -d ':')
  local oui="${mac_upper:0:6}"

  # OUIs de fabricantes IoT conhecidos (Espressif, Tuya/Beken, Shelly, Sonoff, etc.)
  local iot_ouis=(
    # Espressif Systems (ESP8266, ESP32)
    "38A5C9" "4CA919" "20F1B2" "3C0B59" "A4CF12" "30AEA4" "7CDFA1"
    "E89F6D" "246F28" "10521C" "686725" "ECFABC" "CC50E3" "C44F33"
    "840D8E" "D8A01D" "BSSID8" "AC67B2" "94B97E" "F0F5BD" "48E72A"
    "DC4F22" "B4E842" "C84B26" "FC4979" "E065B8"
    # Tuya / Beken (BK7231)
    "BCDF58" "18742E" "E09861" "D82382" "7CF666"
    # Shelly
    "BC351E" "00337A" "508BB9" "E8DB84" "3494B4"
    # Sonoff/ITEAD
    "DC4F22" "A020A6"
    # TP-Link IoT
    "40AE30" "50C7BF" "B0BE76" "3C84A1"
    # Xiaomi/Yeelight
    "64644A" "D4970B" "28EDB4" "9C9960" "F48B32"
    # Philips Hue / Signify
    "001788" "ECB5FA" "00178A"
    # Amazon Echo/Ring
    "44650D" "4C3488" "F0272D" "B47C9C" "A002DC"
    # Google Chromecast/Nest
    "7C2EBD" "6C5AB5" "F88FCA"
    # Broadcom IoT chips
    "B827EB" "DC402A"
  )

  for oui_pattern in "${iot_ouis[@]}"; do
    if [[ "$oui" == "$oui_pattern" ]]; then
      return 0
    fi
  done
  return 1
}

is_iot_by_hostname() {
  local h
  h=$(echo "${HOSTNAME:-}" | tr '[:upper:]' '[:lower:]')
  # Padrões de hostname típicos de firmware embarcado/IoT
  [[ "$h" =~ ^(esp|esp_|esp32|esp8266|tuya|tasmota|shelly|sonoff|ewelink|lwip|smart|iot|plug|bulb|switch|sensor|camera|doorbell|thermostat|zigbee|zwave|wlan0|wlan1|home-[0-9a-f]) ]] && return 0
  # hostname numérico curto ou vazio (típico de IoT sem configuração)
  [[ "$h" == "" || "$h" == "*" ]] && return 1
  return 1
}

add_to_nft() {
  # Idempotente — nft retorna erro se já existir, ignoramos
  /usr/sbin/nft add element $NFT_TABLE $NFT_SET "{ $IP }" 2>/dev/null && return 0 || return 1
}

persist_ip() {
  if ! grep -qxF "$IP" "$PERSIST_FILE" 2>/dev/null; then
    echo "$IP" >> "$PERSIST_FILE"
  fi
}

depersist_ip() {
  [ -f "$PERSIST_FILE" ] || return 0
  grep -vxF "$IP" "$PERSIST_FILE" > "${PERSIST_FILE}.tmp" 2>/dev/null || true
  mv "${PERSIST_FILE}.tmp" "$PERSIST_FILE"
}

remove_from_nft() {
  /usr/sbin/nft delete element $NFT_TABLE $NFT_SET "{ $IP }" 2>/dev/null || true
}

# Só processa add/old (lease novo ou renovação)
if [[ "$ACTION" == "del" ]]; then
  log "lease expirado — mantendo regra nft ativa"
  exit 0
fi

[[ -z "$IP" || -z "$MAC" ]] && exit 0

# Exclusoes explicitas - dispositivos que NUNCA devem ir para bypass IoT
EXCLUDED_MACS=("40:ae:30:81:c7:6e")  # TP-Link AP (TL-WPA4220, nao IoT)
EXCLUDED_IPS=("192.168.15.91")         # AP - sempre fora do bypass
MAC_CLEAN=$(echo "${MAC:-}" | tr [:upper:] [:lower:])
for excl_mac in "${EXCLUDED_MACS[@]}"; do
  if [[ "$MAC_CLEAN" == "$excl_mac" ]]; then
    remove_from_nft
    depersist_ip
    log "EXCLUIDO por MAC ($excl_mac) - nao IoT"
    exit 0
  fi
done
for excl_ip in "${EXCLUDED_IPS[@]}"; do
  if [[ "$IP" == "$excl_ip" ]]; then
    remove_from_nft
    depersist_ip
    log "EXCLUIDO por IP ($excl_ip) - nao IoT"
    exit 0
  fi
done

# Classifica
IS_IOT=0
REASON=""

if is_iot_by_mac; then
  IS_IOT=1
  REASON="MAC_OUI"
fi

if is_iot_by_hostname; then
  IS_IOT=1
  REASON="${REASON:+$REASON+}HOSTNAME"
fi

if [[ "$IS_IOT" -eq 1 ]]; then
  if add_to_nft; then
    persist_ip
    log "DETECTED IoT ($REASON) → adicionado ao bypass nft"
  else
    log "DETECTED IoT ($REASON) → já presente ou erro nft"
  fi
  # Atualiza ip rules via iot-vpn-bypass por MAC (idempotente, async)
  /usr/local/bin/iot-vpn-bypass.sh --add-mac "$MAC" >> "$LOG" 2>&1 &
else
  log "NOT IoT — nenhuma ação"
fi

exit 0
