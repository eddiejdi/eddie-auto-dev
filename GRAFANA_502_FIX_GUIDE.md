# Grafana 502 Bad Gateway - Troubleshooting Guide

**Date**: 21 de abril de 2026  
**Issue**: Grafana retornando HTTP 502 Bad Gateway  
**Status**: 🔴 **INVESTIGATION NEEDED**

---

## Symptom Summary

- URL: http://192.168.15.2:3002 → Connection Timeout (5s+)
- Prometheus: http://192.168.15.2:9090 → Connection Refused
- **Conclusion**: Ambos Grafana e Prometheus estão inacessíveis no homelab

---

## Root Cause Analysis (Possível)

### Cenário 1: Container Frozen (90% probabilidade)
- Grafana Docker container pode estar congelado (já ocorreu em 2026-04-14)
- Prometheus também pode estar congelado ou parado
- Necessita restart manual

### Cenário 2: Port Blocking
- Firewall/ufw bloqueando ports 3002 e 9090
- Network interface down

### Cenário 3: Service Crash
- Processo Grafana/Prometheus morreu
- Nenhum container em execução

---

## Diagnostic Commands (Execute no Homelab 192.168.15.2)

### Step 1: Verificar status dos serviços

```bash
# Se usa Docker:
docker ps --filter name=grafana
docker ps --filter name=prometheus

# Se usa systemd:
systemctl status grafana-server
systemctl status prometheus

# Listar todos containers:
docker ps -a
```

### Step 2: Testar conectividade local

```bash
# Testar Grafana local
curl -I http://localhost:3002/api/health

# Testar Prometheus local  
curl -I http://localhost:9090/-/healthy

# Verificar ports listening
netstat -tlnp | grep -E "3002|9090"
# ou (novo):
ss -tlnp | grep -E "3002|9090"
```

### Step 3: Verificar logs

```bash
# Docker logs:
docker logs grafana --tail 100
docker logs prometheus --tail 100

# Systemd logs:
journalctl -u grafana-server -n 100 --no-paging
journalctl -u prometheus -n 100 --no-paging
```

---

## Solutions

### 🔧 Solution 1: Restart Docker Containers (Se usar Docker)

```bash
# Restart Grafana
docker restart grafana

# Restart Prometheus
docker restart prometheus

# Verify
sleep 5
curl http://localhost:3002/api/health
curl http://localhost:9090/-/healthy
```

### 🔧 Solution 2: Restart Systemd Services (Se usar systemd)

```bash
# Restart Grafana
sudo systemctl restart grafana-server

# Restart Prometheus
sudo systemctl restart prometheus

# Verify
systemctl status grafana-server
systemctl status prometheus
```

### 🔧 Solution 3: Check Firewall

```bash
# Verificar ufw
sudo ufw status
sudo ufw allow 3002
sudo ufw allow 9090

# Verificar iptables (se aplicável)
sudo iptables -L | grep 3002
sudo iptables -L | grep 9090
```

### 🔧 Solution 4: Full Recovery (Se ambos estão parados)

```bash
# Opção A: Docker-compose (se arquivo existe)
cd /path/to/docker-compose
docker-compose restart grafana prometheus

# Opção B: Start from scratch
docker-compose up -d grafana prometheus

# Verify after 10 seconds
sleep 10
docker ps | grep -E "grafana|prometheus"
```

---

## Verification (Após aplicar solução)

Execute no homelab após fix:

```bash
# Teste local
curl -s http://localhost:3002/api/health | jq .
curl -s http://localhost:9090/-/healthy

# Teste remoto (from workstation)
curl -I http://192.168.15.2:3002
curl -I http://192.168.15.2:9090
```

**Expected Output**:
- ✅ Grafana: `HTTP/1.1 200 OK`
- ✅ Prometheus: `HTTP/1.1 200 OK`

---

## Automated Recovery Script

Se tiver acesso shell ao homelab, execute:

```bash
#!/bin/bash
set -e

echo "🔧 Grafana + Prometheus Recovery"

# Detect if docker or systemd
if command -v docker &> /dev/null && docker ps &> /dev/null; then
    echo "Using Docker..."
    docker restart grafana prometheus
    sleep 5
    docker ps | grep -E "grafana|prometheus"
    echo "✅ Docker containers restarted"
else
    echo "Using systemd..."
    sudo systemctl restart grafana-server prometheus
    sleep 5
    systemctl status grafana-server prometheus
    echo "✅ Systemd services restarted"
fi

# Final check
echo ""
echo "Final connectivity test:"
curl -s -m 3 http://localhost:3002/api/health && echo "✅ Grafana OK" || echo "❌ Grafana FAIL"
curl -s -m 3 http://localhost:9090/-/healthy && echo "✅ Prometheus OK" || echo "❌ Prometheus FAIL"
```

---

## Documentation References

- Previous freeze incident: [GRAFANA_FREEZE_RESOLUTION.md](./GRAFANA_FREEZE_RESOLUTION.md)
- Dashboard guide: [grafana/README.md](./grafana/README.md)
- Deployment guide: [docs/GRAFANA_DEPLOYMENT_GUIDE.md](./docs/GRAFANA_DEPLOYMENT_GUIDE.md)

---

## Escalation

If after trying above steps Grafana still doesn't respond:

1. **Check disk space**: `df -h` (if full, cleanup logs/data)
2. **Check memory**: `free -h` (if OOM, restart services)
3. **Check processes**: `ps aux | grep -E "grafana|prometheus"`
4. **Full container restart**: `docker-compose down && docker-compose up -d`
5. **Check network**: `ping 8.8.8.8` (verify internet)
6. **Review container logs for errors**: `docker logs -f grafana 2>&1 | tail -50`

---

**Status**: 🔴 Action required in homelab - Execute diagnostic commands above  
**Next Step**: SSH to homelab and run Step 1-3 diagnostics, then apply appropriate solution

