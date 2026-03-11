#!/bin/bash

echo "=== Diagnóstico de Conectividade ==="
echo "Data: $(date)"
echo ""

# Definir interfaces
IFACE_WIFI="wlp2s0"
IFACE_CABO="enx207bd51a110a"
GATEWAY="192.168.15.1"
DNS1="192.168.15.2"
DNS2="8.8.8.8"
TEST_PING="1.1.1.1"
TEST_DOMAIN="google.com"

echo "[1] Verificando Interfaces de Rede"
ip -brief addr show dev $IFACE_WIFI
ip -brief addr show dev $IFACE_CABO
echo ""

echo "[2] Validando Estado NetworkManager"
nmcli -t -f DEVICE,STATE,CONNECTION device status | grep -E "^($IFACE_WIFI|$IFACE_CABO):"
echo ""

echo "[3] Verificando Tabela de Roteamento"
ip route | grep default || echo "ERRO: Rota padrão não encontrada!"
echo ""

echo "[4] Ping no Gateway ($GATEWAY) - Wi-Fi"
ping -c 3 -W 2 -I $IFACE_WIFI $GATEWAY &> /dev/null
if [ $? -eq 0 ]; then
    echo "Gateway via Wi-Fi: OK"
else
    echo "Gateway via Wi-Fi: FALHOU"
fi

echo "[5] Ping no Gateway ($GATEWAY) - Cabo"
if ip link show dev $IFACE_CABO up &> /dev/null; then
    ping -c 3 -W 2 -I $IFACE_CABO $GATEWAY &> /dev/null
    if [ $? -eq 0 ]; then
        echo "Gateway via Cabo: OK"
    else
        echo "Gateway via Cabo: FALHOU (interface pode estar sem IP)"
    fi
else
    echo "Cabo: Interface DOWN ou inexistente"
fi
echo ""

echo "[6] Teste de DNS e Saída Internet"
ping -c 3 -W 2 $TEST_PING &> /dev/null
if [ $? -eq 0 ]; then
    echo "Saída Internet IP (Ping $TEST_PING): OK"
else
    echo "Saída Internet IP: FALHOU"
fi

ping -c 3 -W 2 $TEST_DOMAIN &> /dev/null
if [ $? -eq 0 ]; then
    echo "Resolução DNS e Saída (Ping $TEST_DOMAIN): OK"
else
    echo "Resolução DNS e Saída: FALHOU"
fi

echo ""
echo "=== Diagnóstico Concluído ==="
