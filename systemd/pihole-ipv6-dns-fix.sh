#!/bin/bash
# Força redirecionamento de DNS IPv6 para Pi-hole
# Corrige IPv6 DNS leak que bypassava Pi-hole na rede local
# Criado em 2026-03-04
#
# Problema: dispositivos na rede local usavam IPv6 DNS do roteador VIVOFIBRA
# via Router Advertisement (RA), bypassando o Pi-hole. Via VPN funcionava
# porque o WireGuard forçava todo DNS pelo túnel IPv4 para o Pi-hole.
#
# Solução: ip6tables DNAT para redirecionar DNS IPv6 para o Pi-hole +
# radvd para anunciar Pi-hole como DNS IPv6 via RA.

set -euo pipefail

PIHOLE_IPV6="2804:7f0:9342:bca1:2e0:4cff:feb6:3d5e"
PIHOLE_IPV6_LL="fe80::2e0:4cff:feb6:3d5e"

# IPv6 DNAT - redireciona DNS (porta 53) para Pi-hole
# Regras com endereço global
ip6tables -t nat -C PREROUTING -p udp --dport 53 ! -d "$PIHOLE_IPV6" \
  -j DNAT --to-destination "[$PIHOLE_IPV6]:53" 2>/dev/null || \
ip6tables -t nat -I PREROUTING 1 -p udp --dport 53 ! -d "$PIHOLE_IPV6" \
  -j DNAT --to-destination "[$PIHOLE_IPV6]:53"

ip6tables -t nat -C PREROUTING -p tcp --dport 53 ! -d "$PIHOLE_IPV6" \
  -j DNAT --to-destination "[$PIHOLE_IPV6]:53" 2>/dev/null || \
ip6tables -t nat -I PREROUTING 2 -p tcp --dport 53 ! -d "$PIHOLE_IPV6" \
  -j DNAT --to-destination "[$PIHOLE_IPV6]:53"

# Regras com link-local
ip6tables -t nat -C PREROUTING -p udp --dport 53 ! -d "$PIHOLE_IPV6_LL" \
  -j DNAT --to-destination "[$PIHOLE_IPV6_LL]:53" 2>/dev/null || \
ip6tables -t nat -I PREROUTING 3 -p udp --dport 53 ! -d "$PIHOLE_IPV6_LL" \
  -j DNAT --to-destination "[$PIHOLE_IPV6_LL]:53"

# MASQUERADE para respostas DNS voltarem corretamente
ip6tables -t nat -C POSTROUTING -p udp --dport 53 -j MASQUERADE 2>/dev/null || \
ip6tables -t nat -A POSTROUTING -p udp --dport 53 -j MASQUERADE

ip6tables -t nat -C POSTROUTING -p tcp --dport 53 -j MASQUERADE 2>/dev/null || \
ip6tables -t nat -A POSTROUTING -p tcp --dport 53 -j MASQUERADE

echo "[$(date)] Pi-hole IPv6 DNS fix aplicado"
