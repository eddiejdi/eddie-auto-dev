#!/bin/bash
# setup-qos.sh — QoS com priorização VPN + balanceamento igualitário por host
# Correção 2026-05-02: tc qdisc replace (era add) → resolve NLM_F_REPLACE no boot
# Adição 2026-05-02: CAKE dual-srchost para fair-share por host + IFB ingress shaping
set -euo pipefail

WAN="eth-onboard"
WG_IF="wg0"
NORD_IF="nordlynx"
IFB="ifb0"

# Velocidade real do ISP (Vivo GPON) — ajuste se mudar de plano
ISP_DOWN="10mbit"
ISP_UP="5mbit"

# ──────────────────────────────────────────────
# Limpeza idempotente
# ──────────────────────────────────────────────
cleanup() {
  tc qdisc del root dev "$WAN" 2>/dev/null || true
  tc qdisc del ingress dev "$WAN" 2>/dev/null || true
  tc qdisc del root dev "$IFB" 2>/dev/null || true
  ip link set dev "$IFB" down 2>/dev/null || true

  iptables -t mangle -D OUTPUT      -o "$WG_IF"   -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$NORD_IF" -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WG_IF"   -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$NORD_IF" -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --dport 23456 -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --dport 7844  -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --dport 23456 -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --dport 7844  -j MARK --set-mark 2 2>/dev/null || true
}

ensure_mark_rule() {
  local table="$1" chain="$2"
  local rule=("${@:3}")
  iptables -t "$table" -C "$chain" "${rule[@]}" 2>/dev/null || \
    iptables -t "$table" -A "$chain" "${rule[@]}"
}

# ──────────────────────────────────────────────
# Setup IFB para shaping de ingresso (download)
# ──────────────────────────────────────────────
setup_ifb() {
  modprobe ifb numifbs=1 2>/dev/null || true
  ip link set dev "$IFB" up 2>/dev/null || true

  # Redireciona ingresso do WAN para o IFB
  tc qdisc replace dev "$WAN" ingress handle ffff:
  tc filter replace dev "$WAN" parent ffff: protocol ip u32 \
    match u32 0 0 action mirred egress redirect dev "$IFB"

  # CAKE no IFB: limita download + balanceamento por IP de destino (host que recebe)
  tc qdisc replace dev "$IFB" root cake \
    bandwidth "$ISP_DOWN" \
    besteffort \
    dual-dsthost \
    nat \
    wash \
    no-split-gso
}

# ──────────────────────────────────────────────
# Limpeza inicial
# ──────────────────────────────────────────────
cleanup

# ──────────────────────────────────────────────
# EGRESSO (upload): HTB root para priorização VPN
# ──────────────────────────────────────────────
# FIX: "replace" em vez de "add" → evita NLM_F_REPLACE no boot quando
# o kernel/systemd-networkd já instalou fq_codel como qdisc padrão
tc qdisc replace dev "$WAN" root handle 1: htb default 30

tc class add dev "$WAN" parent 1: classid 1:1 htb rate "$ISP_UP" ceil "$ISP_UP"

# 1:10 — WireGuard (trabalho): prioridade máxima
tc class add dev "$WAN" parent 1:1 classid 1:10 htb rate 2mbit ceil "$ISP_UP" prio 1
# 1:20 — NordVPN (navegação): prioridade média
tc class add dev "$WAN" parent 1:1 classid 1:20 htb rate 1500kbit ceil "$ISP_UP" prio 2
# 1:30 — Tráfego geral LAN: CAKE para fair-share igualitário por host de origem
tc class add dev "$WAN" parent 1:1 classid 1:30 htb rate 1mbit ceil "$ISP_UP" prio 3
# 1:40 — Storj node: limitado para não saturar uplink ISP
tc class add dev "$WAN" parent 1:1 classid 1:40 htb rate 400kbit ceil 600kbit prio 4

# ──────────────────────────────────────────────
# Leaf qdiscs: CAKE para fair-share por host em cada classe
# ──────────────────────────────────────────────
# Wireguard e NordVPN: fq_codel (tráfego já tunelado, um host de origem)
tc qdisc add dev "$WAN" parent 1:10 fq_codel
tc qdisc add dev "$WAN" parent 1:20 fq_codel

# Classe geral (1:30): CAKE com dual-srchost → divide igualmente por IP de origem
# "nat" resolve NATed IPs para o host LAN real antes de classificar
tc qdisc add dev "$WAN" parent 1:30 cake \
  bandwidth "$ISP_UP" \
  besteffort \
  dual-srchost \
  nat \
  wash \
  no-split-gso

# Storj: fq_codel simples (IP único, limitado pelo HTB pai)
tc qdisc add dev "$WAN" parent 1:40 fq_codel

# ──────────────────────────────────────────────
# Marcação de pacotes (iptables mangle)
# ──────────────────────────────────────────────
ensure_mark_rule mangle OUTPUT      -o "$WG_IF"   -j MARK --set-mark 1
ensure_mark_rule mangle OUTPUT      -o "$NORD_IF" -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WG_IF"   -j MARK --set-mark 1
ensure_mark_rule mangle POSTROUTING -o "$NORD_IF" -j MARK --set-mark 2

ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1
ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --dport 23456  -j MARK --set-mark 2
ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --dport 7844   -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --dport 23456  -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --dport 7844   -j MARK --set-mark 2

# ──────────────────────────────────────────────
# Filtros HTB por marca de pacote
# ──────────────────────────────────────────────
tc filter add dev "$WAN" parent 1: protocol ip prio 1 handle 1 fw classid 1:10
tc filter add dev "$WAN" parent 1: protocol ip prio 2 handle 2 fw classid 1:20
# Storj (IP fixo, tem prioridade de filtro mais alta que o default)
tc filter add dev "$WAN" protocol ip parent 1: prio 3 u32 \
  match ip src 192.168.15.250/32 flowid 1:40
# Tráfego sem marca → default 1:30 (CAKE fair-share)

# ──────────────────────────────────────────────
# Ingress shaping (download) via IFB
# ──────────────────────────────────────────────
setup_ifb

cat <<EOF
QoS configurado com sucesso:
  EGRESSO (upload $ISP_UP):
    1:10 → WireGuard (trabalho)     — prioridade 1, fq_codel
    1:20 → NordVPN (navegação)      — prioridade 2, fq_codel
    1:30 → LAN geral (default)      — prioridade 3, CAKE dual-srchost (fair por host)
    1:40 → Storj (192.168.15.250)   — prioridade 4, limitado 400kbit

  INGRESSO (download $ISP_DOWN):
    IFB CAKE dual-dsthost + nat     — fair share igualitário por host receptor

  Bug corrigido: tc qdisc replace (evita NLM_F_REPLACE no boot)
EOF
