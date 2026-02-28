# 📋 Deployment Checklist — Ollama Monitoring & Auto-Recovery

> **Propósito**: Validar que scripts de monitoramento foram corretamente instalados e ativados como serviços systemd depois de desenvolvidos.
>
> **Aplicável Quando**: Após criar novo script em `tools/selfheal/`, antes de marcar tarefa como "DONE"

---

## 🚀 Checklist Antes de Push para Main

### Fase 1: Local Development ✅
```bash
# [ ] Script criado e testado localmente
#     File: tools/selfheal/ollama_frozen_monitor.sh
#     Test: chmod +x script.sh && ./script.sh [args]

# [ ] Script tem shebang e set -euo pipefail
grep -E "^#!/bin/bash|set -euo pipefail" tools/selfheal/ollama_frozen_monitor.sh

# [ ] Sem hardcoded paths absolutos (usar env vars)
grep -v "^#" tools/selfheal/ollama_frozen_monitor.sh | grep -E "^/home|^/root" && echo "⚠️ HARDCODED PATH FOUND" || echo "✅ OK"

# [ ] Commit local com mensagem descritiva
git add tools/selfheal/ollama_frozen_monitor.sh
git commit -m "feat(selfheal): add ollama frozen detection & auto-recovery script"
```

### Fase 2: Pre-Deploy Documentation ✅
```bash
# [ ] Documentação criada: SELFHEALING_SETUP.md ou similar
# [ ] README do script inclui:
#     - Propósito
#     - Parâmetros esperados
#     - Saída esperada
#     - Como testar localmente
# [ ] Systemd service file template documentado com:
#     - User/Group necessários
#     - After=/Wants= dependências
#     - Restart policy
```

---

## 🔥 Checklist Pós-Commit (Deployment ao Homelab)

### Fase 3: Transfer & Install ⭐ CRÍTICA
```bash
# [ ] SCP script para homelab
scp tools/selfheal/ollama_frozen_monitor.sh \
    homelab@192.168.15.2:/tmp/ollama_frozen_monitor.sh
#     Status: Transferred 5758 bytes

# [ ] SSH install para /usr/local/bin
ssh homelab@192.168.15.2 "sudo mv /tmp/ollama_frozen_monitor.sh /usr/local/bin/ && \
                          sudo chmod +x /usr/local/bin/ollama_frozen_monitor && \
                          ls -lh /usr/local/bin/ollama_frozen_monitor"
#     Expected: -rwxr-xr-x ... ollama_frozen_monitor

# [ ] Verify script é executável
ssh homelab@192.168.15.2 "/usr/local/bin/ollama_frozen_monitor --help 2>&1 | head -5"
#     Expected: Help ou primeiras linhas do script
```

### Fase 4: Systemd Service Creation ⭐ CRÍTICA
```bash
# [ ] Criar service file no homelab
ssh homelab@192.168.15.2 'sudo tee /etc/systemd/system/ollama-frozen-monitor.service > /dev/null' << 'EOF'
[Unit]
Description=Ollama Frozen State Detection & Auto-Recovery
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/ollama_frozen_monitor 180 15 3 60
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# [ ] Daemon reload
ssh homelab@192.168.15.2 "sudo systemctl daemon-reload"
#     Expected: (sem output, exit code 0)

# [ ] Enable para boot automático
ssh homelab@192.168.15.2 "sudo systemctl enable ollama-frozen-monitor.service"
#     Expected: Created symlink in /etc/systemd/system/multi-user.target.wants/

# [ ] Start o serviço
ssh homelab@192.168.15.2 "sudo systemctl start ollama-frozen-monitor.service"
#     Expected: (sem output, exit code 0)
```

### Fase 5: Validation & Verification ⭐ CRÍTICA
```bash
# [ ] Verify service status
ssh homelab@192.168.15.2 "sudo systemctl status ollama-frozen-monitor.service --no-pager"
#     Expected: ● ollama-frozen-monitor.service - Ollama Frozen...
#               Loaded: loaded (/etc/systemd/system/ollama-frozen-monitor.service; enabled; preset: disabled)
#               Active: active (running) ← KEY LINE
#               Since: 2026-02-28 18:03:00 UTC; 2s ago

# [ ] Check service is-active command
ssh homelab@192.168.15.2 "sudo systemctl is-active ollama-frozen-monitor.service"
#     Expected: active

# [ ] Check startup logs
ssh homelab@192.168.15.2 "sudo journalctl -u ollama-frozen-monitor.service -n 10 --no-pager"
#     Expected: (logs mostrando execução do script)

# [ ] Verify output files estão sendo criados
ssh homelab@192.168.15.2 "ls -lh /tmp/ollama_*.txt /tmp/ollama_*.prom 2>/dev/null | head -10"
#     Expected: -rw-r--r-- ... /tmp/ollama_metrics.prom (2.1K)
#              -rw-r--r-- ... /tmp/ollama_metrics.txt (578B)

# [ ] Metrics file atualizado recentemente (< 30 segundos)
ssh homelab@192.168.15.2 "stat /tmp/ollama_metrics.prom | grep Modify"
#     Expected: Modify: 2026-02-28 18:05:45.123456789 UTC ← recent
```

### Fase 6: Functional Test (Optional but Recommended)
```bash
# [ ] Simular congelamento (apenas se você tiver acesso ao homelab)
# ⚠️ CUIDADO: Isto vai pausar o Ollama por 3+ minutos
# ssh homelab@192.168.15.2 "sudo pkill -STOP ollama && sleep 200 && sudo pkill -CONT ollama"
# 
# Depois monitorar:
# ssh homelab@192.168.15.2 "sudo journalctl -u ollama-frozen-monitor -f --since='now'"
#
# [ ] Verificar métrica aumentou
# ssh homelab@192.168.15.2 "cat /tmp/ollama_metrics.txt | grep ollama_selfheal_restarts_total"
#     Expected: ollama_selfheal_restarts_total 1
```

---

## 📝 Post-Deployment Documentation

### Após Completar Todas as Etapas
```bash
# [ ] Update SELFHEALING_SETUP.md com timestamp de deploy
# [ ] Add "Verified Deployment" section com:
#     - Data/hora do deploy
#     - Resultado de cada verificação
#     - Service status screenshot (systemctl status)
# [ ] Create deployment log entry

cat >> DEPLOYMENT_LOG.md << 'EOF'
## 2026-02-28 Ollama Frozen Monitor Deployment

**Time**: 18:02 UTC
**Services Deployed**:
- ✅ ollama-frozen-monitor.service (active)
- ✅ ollama-metrics-exporter.service (active)

**Verification**:
- systemctl is-active: active (both)
- Metrics export: /tmp/ollama_metrics.prom (2.1K, updated every 15s)
- Auto-recovery threshold: 180s frozen → restart

**Status**: READY FOR PRODUCTION
EOF
```

---

## 🔄 Multi-Script Deployment (quando há vários scripts)

Se você tem `tools/selfheal/*.sh` com múltiplos scripts:

```bash
#!/bin/bash
# Batch Deploy Script for Selfhealing Services

HOMELAB_USER="homelab"
HOMELAB_HOST="192.168.15.2"
SCRIPTS=("ollama_frozen_monitor.sh" "ollama_metrics_exporter.sh")

function deploy_script() {
    local script=$1
    echo "📦 Deploying $script..."
    
    # Transfer
    scp "tools/selfheal/$script" "$HOMELAB_USER@$HOMELAB_HOST:/tmp/"
    
    # Install
    ssh "$HOMELAB_USER@$HOMELAB_HOST" "sudo mv /tmp/$script /usr/local/bin/ && \
                                       sudo chmod +x /usr/local/bin/$script"
    
    # Verify
    ssh "$HOMELAB_USER@$HOMELAB_HOST" "ls -lh /usr/local/bin/$script"
}

for script in "${SCRIPTS[@]}"; do
    deploy_script "$script" || exit 1
done

echo "✅ All scripts deployed"
```

---

## 🆘 Troubleshooting Checklist

Se `systemctl status` mostra **"inactive"** ou **"failed"**:

```bash
# [ ] Verificar logs de erro
ssh homelab@192.168.15.2 "sudo journalctl -u ollama-frozen-monitor -n 50 --no-pager | tail -20"

# Problemas comuns:

### "Unit file not found"
→ Criação do service file falhou
→ Re-execute: ssh homelab "sudo tee /etc/systemd/system/... < EOF"
→ Depois: sudo systemctl daemon-reload

### "Permission denied"
→ Script não tem +x permission
→ Fix: ssh homelab "sudo chmod +x /usr/local/bin/ollama_*"

### "Service is not active"
→ Pode ser erro no script (não inicial com #!/bin/bash, não é executável, etc.)
→ Test: ssh homelab "/usr/local/bin/ollama_frozen_monitor [args]"

### "/var/log/ not found" or "tmp/ permission denied"
→ User=ollama não tem write permission
→ Fix: Change User=root em service file
→ Re-Deploy: sudo systemctl stop && recriar service file && systemctl start

### "ExecStart /usr/local/bin/ollama_frozen_monitor: No such file or directory"
→ Script não foi copiado para /usr/local/bin
→ Fix: Re-run SCP transfer
→ Verify: ssh homelab "ls -lh /usr/local/bin/ollama_*"
```

---

## 🎯 Resumo (O que não deve ser esquecido)

**ANTES de marcar uma tarefa como DONE:**

1. ✅ Script testado localmente (chmod +x, ./script)
2. ✅ SCP script para `/tmp/` no homelab
3. ✅ SSH move para `/usr/local/bin/` + chmod +x
4. ✅ SSH create service file em `/etc/systemd/system/`
5. ✅ SSH systemctl daemon-reload
6. ✅ SSH systemctl enable
7. ✅ SSH systemctl start
8. ✅ SSH systemctl is-active (deve retornar "active")
9. ✅ SSH journalctl para verificar logs
10. ✅ Documentar timestamp em DEPLOYMENT_LOG.md

**Se qualquer um destes passos for pulado = risco de "scripts mortos" no git**

---

Última atualização: 2026-02-28 18:05 UTC
