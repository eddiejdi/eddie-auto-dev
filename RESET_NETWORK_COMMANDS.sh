#!/bin/bash
# COMANDOS DE RESET DE REDE - EXECUTE NO SERVIDOR 192.168.15.2
# Copie e cole estes comandos no console local/IPMI/Proxmox do servidor

echo "=================================================="
echo "RESET DE REDE E RECUPERAÇÃO DO SERVIDOR"
echo "=================================================="

# 1. PARAR SERVIÇO PROBLEMÁTICO
echo ""
echo "1️⃣ Parando agent-network-exporter..."
sudo systemctl stop agent-network-exporter
sudo systemctl disable agent-network-exporter
sudo rm -f /etc/systemd/system/agent-network-exporter.service
sudo systemctl daemon-reload
echo "✅ Serviço parado e removido"

# 2. RESETAR REDE
echo ""
echo "2️⃣ Resetando interfaces de rede..."
sudo systemctl restart networking
sleep 2
echo "✅ Rede reiniciada"

# 3. LIMPAR CACHE DNS
echo ""
echo "3️⃣ Limpando cache DNS..."
sudo systemctl restart systemd-resolved
sleep 2
echo "✅ DNS limpo"

# 4. RESTAURAR SSH
echo ""
echo "4️⃣ Restaurando SSH..."
sudo systemctl restart ssh
sleep 2
echo "✅ SSH restaurado"

# 5. VERIFICAR STATUS
echo ""
echo "5️⃣ Verificando status..."
echo ""
echo "🔹 Interface de rede:"
ip addr show | grep -E "inet |interface"
echo ""
echo "🔹 Rota padrão:"
ip route show default
echo ""
echo "🔹 SSH Status:"
sudo systemctl status ssh --no-pager | head -5
echo ""
echo "🔹 Serviços críticos:"
sudo systemctl status specialized-agents-api eddie-coordinator --no-pager | grep -E "Active|●"

echo ""
echo "=================================================="
echo "✅ RECUPERAÇÃO CONCLUÍDA"
echo "=================================================="
echo ""
echo "Teste de conectividade:"
echo "  ping 192.168.15.1  (gateway)"
echo "  ping 8.8.8.8       (internet)"
echo ""
echo "Teste SSH (do client):"
echo "  ssh homelab@192.168.15.2 'echo OK'"
echo ""
