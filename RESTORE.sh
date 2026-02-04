#!/bin/bash
# RESTORE SCRIPT - Execute no servidor em modo emergência
# Restaura funcionamento pleno após crash do agent-network-exporter

set -e

echo "========================================================"
echo "RESTAURAÇÃO DO SERVIDOR - MODO EMERGÊNCIA"
echo "========================================================"

echo ""
echo "1️⃣  Parando agent-network-exporter..."
systemctl stop agent-network-exporter 2>/dev/null || echo "   (não estava rodando)"

echo "2️⃣  Desabilitando serviço..."
systemctl disable agent-network-exporter 2>/dev/null || echo "   (não estava habilitado)"

echo "3️⃣  Removendo arquivo de serviço..."
rm -f /etc/systemd/system/agent-network-exporter.service
systemctl daemon-reload

echo "4️⃣  Reiniciando SSH..."
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || echo "   (SSH ok)"

echo "5️⃣  Verificando serviços essenciais..."
echo "   - PostgreSQL:"
systemctl status eddie-postgres --no-pager 2>/dev/null | grep -E "Active:|running" || echo "     (não rodando)"

echo "   - Specialized Agents API:"
systemctl status specialized-agents-api --no-pager 2>/dev/null | grep -E "Active:|running" || echo "     (não rodando)"

echo "   - Coordinator:"
systemctl status eddie-coordinator --no-pager 2>/dev/null | grep -E "Active:|running" || echo "     (não rodando)"

echo ""
echo "6️⃣  Testando conectividade..."
ping -c 1 192.168.15.1 >/dev/null 2>&1 && echo "   ✅ Gateway OK" || echo "   ❌ Gateway não responde"
ip a | grep -E "inet " | head -3

echo ""
echo "========================================================"
echo "✅ RESTAURAÇÃO CONCLUÍDA"
echo "========================================================"
echo ""
echo "Próximos passos:"
echo "1. Reinicie o servidor para mudar de volta do IP emergência:"
echo "   sudo reboot"
echo ""
echo "2. Aguarde retornar ao IP 192.168.15.2"
echo ""
