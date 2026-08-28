# Deployment Guide: RPA4All Snapshot Watchdog System

## Arquitetura Proposta

```
create_snapshot.sh (backup longo ~18min)
    ↓
rpa4all-snapshot.service (com timeout 30min)
    ↓ (falha?)
    └→ OnFailure: rpa4all-snapshot-recovery.service (retry em 5min)
    
rpa4all-snapshot-health.timer (a cada 5min)
    ↓
rpa4all-snapshot-health.service (verifica travamento)
    ├─ Se travado: Reinicia rpa4all-snapshot.service
    └─ Se OK: Log e exit 0
```

## Arquivos a Criar/Modificar

### 1. Aumentar timeout no create_snapshot.sh
```bash
# No início do script, adicionar lock file:
LOCK_FILE="/tmp/rpa4all-snapshot.lock"
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT
```

### 2. Copiar para homelab
```bash
ssh homelab@192.168.15.2 << 'DEPLOY'

# 1. Atualizar serviço principal
sudo tee /etc/systemd/system/rpa4all-snapshot.service > /dev/null << 'SERVICE'
[Unit]
Description=Run rpa4all snapshot
Wants=network-online.target
After=network-online.target
OnFailure=rpa4all-snapshot-recovery.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/create_snapshot.sh
TimeoutStartSec=1800
TimeoutStopSec=300

[Install]
WantedBy=multi-user.target
SERVICE

# 2. Health check script
sudo tee /usr/local/bin/rpa4all-snapshot-health.sh > /dev/null << 'HEALTH'
#!/bin/bash
set -euo pipefail
LOCK_FILE="/tmp/rpa4all-snapshot.lock"
MAX_AGE_SECS=1800

if systemctl is-active --quiet rpa4all-snapshot.service; then
    echo "✓ Rodando"
    exit 0
fi

if [[ -f "$LOCK_FILE" ]]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [[ $LOCK_AGE -gt $MAX_AGE_SECS ]]; then
        echo "⚠ TRAVAMENTO! Reiniciando..."
        systemctl restart rpa4all-snapshot.service
        exit 1
    fi
    rm -f "$LOCK_FILE"
fi
exit 0
HEALTH

sudo chmod +x /usr/local/bin/rpa4all-snapshot-health.sh

# 3. Health check service
sudo tee /etc/systemd/system/rpa4all-snapshot-health.service > /dev/null << 'HEALTH_SVC'
[Unit]
Description=Health check for rpa4all snapshot
After=rpa4all-snapshot.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/rpa4all-snapshot-health.sh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rpa4all-snapshot-health
HEALTH_SVC

# 4. Health check timer
sudo tee /etc/systemd/system/rpa4all-snapshot-health.timer > /dev/null << 'HEALTH_TIMER'
[Unit]
Description=Health check timer
Requires=rpa4all-snapshot-health.service

[Timer]
OnBootSec=60s
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
HEALTH_TIMER

# 5. Recovery service
sudo tee /etc/systemd/system/rpa4all-snapshot-recovery.service > /dev/null << 'RECOVERY'
[Unit]
Description=Recovery handler
PartOf=rpa4all-snapshot.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'sleep 300; systemctl restart rpa4all-snapshot.service'
StandardOutput=journal
StandardError=journal
RECOVERY

# 6. Reload e ativar
sudo systemctl daemon-reload
sudo systemctl enable rpa4all-snapshot-health.timer
sudo systemctl start rpa4all-snapshot-health.timer

# 7. Verificar status
systemctl status rpa4all-snapshot.service rpa4all-snapshot-health.timer
systemctl list-timers rpa4all-snapshot*

DEPLOY
```

## Teste

```bash
# Terminal 1: Monitorar logs
ssh homelab@192.168.15.2 'journalctl -u rpa4all-snapshot* -f'

# Terminal 2: Forçar execução
ssh homelab@192.168.15.2 'sudo systemctl start rpa4all-snapshot.service'

# Verificar:
# 1. Inicia o backup
# 2. Health check detecta se travado
# 3. Reinicia automaticamente se timeout
```

## Benefícios

✅ **Auto-recovery** em caso de travamento
✅ **Detecção periódica** a cada 5 minutos
✅ **Timeout apropriado** para operação longa
✅ **Logs estruturados** via journalctl
✅ **Sem intervenção manual**
✅ **Observabilidade** via systemd

## Monitoramento

```bash
# Ver últimos health checks
journalctl -u rpa4all-snapshot-health.service -n 20

# Ver falhas
journalctl -u rpa4all-snapshot.service --grep="Failed\|killed"

# Ver recuperações
journalctl -u rpa4all-snapshot-recovery.service
```
