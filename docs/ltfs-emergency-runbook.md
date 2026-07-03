# Runbook: LTFS Emergência — HP LTO-6 no NAS (192.168.15.4)

> **Versão:** 2026-06-28 · Atualizado após incidente EOD missing + recovery dual-drive

---

## Arquitetura atual (pós-2026-06-23)

| Drive | SCSI | nst | Volser | Mountpoint | Serviço |
|-------|------|-----|--------|-----------|---------|
| LTO-6 primário | `/dev/sg3` | `/dev/nst0` | SG1R26 | `/mnt/tape/lto6` | `ltfs-lto6.service` |
| LTO-6 secundário | `/dev/sg5` | `/dev/st2` | — | `/mnt/tape/lto6b` | `ltfs-lto6b.service` (disabled) |

**Orchestrator na NAS:** `/var/db/ltfs-tools/ltfs_recovery.py`  
**Env file na NAS:** `/etc/default/ltfs-lto6`  
**LTFS binários:** `/var/db/ltfs-patched/bin/`  
**FC hosts:** `host7`, `host8` (QLogic ISP2532)

### Como executar o orchestrator na NAS

```bash
# SEMPRE como root via SSH (truenas_admin não tem sudo passwordless):
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --<modo>"

# Exemplos:
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --diagnose"
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --check"
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --deep-recovery"
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --orchestrated-mount"
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --orchestrated-stop"
```

> **⚠️ Nunca rode o orchestrator localmente no homelab** — ele chama `/dev/sg3` e `ltfsck` que não existem fora da NAS. O lock `/run/lock/ltfs-orchestrator.lock` também requer root.

### Reconciliação pós-boot / pós-queda (`--boot-reconcile`)

Após queda de energia ou reboot no meio de uma operação orquestrada, o estado pode ficar inconsistente: units mascaradas em runtime (`systemctl mask --runtime`), `suspended-units.json` órfão e lockfiles de PID morto. O modo `--boot-reconcile` corrige tudo isso **sem tocar na fita**:

```bash
ssh root@192.168.15.4 "set -a; . /etc/default/ltfs-lto6; set +a; python3 /var/db/ltfs-tools/ltfs_recovery.py --boot-reconcile"
```

O que ele faz: (1) remove lockfiles cujo PID está morto; (2) restaura units suspensas registradas no state file; (3) desmascara máscaras `--runtime` residuais do `ltfs-lto6.service`/escalator/timers; (4) detecta cursores de escrita órfãos e **alerta via Telegram sem agir** — a decisão de `--cursor-recover` é humana. Roda automaticamente no boot via `ltfs-boot-reconcile.service` (antes do mount e do checkpoint-recover).

O state file de suspensão agora é persistente: `/var/lib/ltfs/suspended-units.json` (o caminho legado `/run/ltfs-recovery/suspended-units.json` ainda é lido como fallback).

### Hierarquia de locks (fonte de verdade)

| Lock | Dono | Propósito |
|------|------|-----------|
| `/run/lock/ltfs-orchestrator.lock` | `ltfs_recovery.py` (`_exclusive_tape_lock`) e `ltfs-buffer-flush.sh` | Exclusividade de operações orquestradas (mount/stop/recovery/flush) |
| `/run/lock/ltfs-tape-exclusive.lock` | `ltfs-fc-stable-start` | Serializa o start do processo LTFS |
| `/run/lock/tape-access.lock` | `tape-access` (fila FIFO em `/run/tape-queue/`) | Gate de acesso para jobs de drain/backup |

Todos são limpos pelo `--boot-reconcile` quando o PID dono está morto. Não criar novos lockfiles — reutilizar o orchestrator.

### Serviços NAS relacionados

```bash
# NFS export da fita para a rede:
systemctl status ltfs-nfs-export.service     # deve estar active após mount
systemctl start  ltfs-nfs-export.service

# Verificar export ativo:
exportfs -v   # deve mostrar /mnt/tape/lto6 → 192.168.15.0/24
```

> **Nota:** `ltfs-idle-unmount.timer` e `ltfs-cache-flush.timer` não existem na NAS — o orchestrator tenta mascarar/desmascarar mas os unit files não estão lá. Ignorar erros "No such file or directory" para esses serviços.

---

---

## Acesso ao NAS

```bash
ssh root@192.168.15.4
# ou via truenas_admin (sem sudo):
ssh truenas_admin@192.168.15.4
```

---

## Nível 1 — Verificação rápida (2 min)

```bash
# No NAS (root):
ssh root@192.168.15.4 "
  systemctl is-active ltfs-lto6.service
  mount | grep ltfs
  df -h /mnt/tape/lto6 /mnt/tape/lto6b
  cat /mnt/tape/lto6/.ltfs-ready 2>/dev/null && echo ready-file OK
"
```

Se tudo OK → encerrar. Se não:

---

## Nível 2 — Diagnóstico (5 min)

```bash
ssh root@192.168.15.4 "
  # 1. Drives SCSI respondem?
  sg_inq /dev/sg3   # lto6 primário
  sg_inq /dev/sg5   # lto6b secundário

  # Se sg_inq travar/falhar: reset LIP do FC
  echo 1 > /sys/class/fc_host/host7/issue_lip && sleep 5

  # 2. FC Online?
  cat /sys/class/fc_host/host7/port_state   # esperado: Online
  cat /sys/class/fc_host/host8/port_state

  # 3. Fita carregada (lto6 = sg3/nst0)?
  mt -f /dev/nst0 status | head -8           # deve ter BOT e ONLINE

  # 4. TapeAlert (problema de mídia)?
  sg_logs /dev/sg3 -p 0x2e | grep ': 1'    # flags setados = problema físico

  # 5. Capacidade (dados presentes na fita?):
  sg_logs /dev/sg3 -p 0x31 | grep -E 'Main.*remaining|Alternate.*remaining'
  # Main remaining == Main maximum  → fita VAZIA
  # Alternate remaining < maximum   → há dados escritos

  # 6. Log do serviço LTFS:
  tail -30 /var/log/ltfs-lto6.log

  # 7. Diagnose via orchestrator:
  set -a; . /etc/default/ltfs-lto6; set +a
  python3 /var/db/ltfs-tools/ltfs_recovery.py --diagnose
"

---

## Nível 3 — Recuperação LTFS corrompido

> **Regra:** todas as operações de fita passam pelo orchestrator. Nunca chamar `ltfsck`, `fusermount` ou `pkill ltfs` diretamente.

### Caso A: `LTFS17146E EOD of DP(1) is missing` — deep recovery

Este erro aparece no `/var/log/ltfs-lto6.log` quando o mount falha. Pode ser **transiente** (causado por parada abrupta): o `--deep-recovery` pode descobrir que ambos os EODs já estão presentes e montar normalmente.

```bash
# 1. Deep recovery via orchestrator (pode levar de 1 min a horas):
ssh root@192.168.15.4 "
  set -a; . /etc/default/ltfs-lto6; set +a
  python3 /var/db/ltfs-tools/ltfs_recovery.py --deep-recovery
"

# Verificar resultado no JSON: success=true + 'Volume is consistent'
# Se 'Both EODs are detected. A deep recovery operation is unnecessary.'
# → erro era transiente; volume OK

# 2. Após deep recovery, montar:
ssh root@192.168.15.4 "
  set -a; . /etc/default/ltfs-lto6; set +a
  python3 /var/db/ltfs-tools/ltfs_recovery.py --orchestrated-mount
"

# 3. Reiniciar via systemd (para supervisão correta):
ssh root@192.168.15.4 "
  systemctl reset-failed ltfs-lto6.service
  systemctl start ltfs-lto6.service
  systemctl start ltfs-nfs-export.service
"
```

### Caso B: `ltfs-lto6.service` inactive, sem erro no log

```bash
ssh root@192.168.15.4 "
  systemctl reset-failed ltfs-lto6.service
  systemctl start ltfs-lto6.service
  systemctl start ltfs-nfs-export.service
  systemctl is-active ltfs-lto6.service
  mount | grep ltfs
"
```

### Caso C: LTFS trava ao montar (FUSE pendurado)

```bash
# Via orchestrator (não pkill/fusermount direto):
ssh root@192.168.15.4 "
  set -a; . /etc/default/ltfs-lto6; set +a
  python3 /var/db/ltfs-tools/ltfs_recovery.py --orchestrated-stop
  sleep 5
  systemctl reset-failed ltfs-lto6.service
  systemctl start ltfs-lto6.service
  systemctl start ltfs-nfs-export.service
"
```

---

## Nível 4 — LOCATE -20301 (BOT markers corrompidos) ou reformatação

> **⚠️ Este é o caminho MAIS RÁPIDO quando você vê `-20301` em qualquer ltfsck ou mount attempt.**

### Confirmar antes de reformatar:

```bash
ssh root@192.168.15.4 "sg_logs /dev/sg3 -p 0x31 | grep -E 'Main.*remaining|Alternate.*remaining'"
```

- Se `Alternate remaining ≈ Alternate maximum` → **fita vazia** → reformatar sem risco.
- Se `Alternate remaining < maximum` → há dados → confirmar com usuário antes de reformatar.

### Reformatação via orchestrator:

```bash
ssh root@192.168.15.4 "
  set -a; . /etc/default/ltfs-lto6; set +a
  python3 /var/db/ltfs-tools/ltfs_recovery.py --reformat
"
# O orchestrator usa EXATAMENTE 6 chars no serial (ex: HUJ548 para HUJ5485704)
# Duração: ~5-10 min. Após sucesso, montar:
ssh root@192.168.15.4 "
  systemctl reset-failed ltfs-lto6.service
  systemctl start ltfs-lto6.service
  systemctl start ltfs-nfs-export.service
"
```

---

## Nível 5 — Drive não responde ao sg_inq (HBA/FC)

```bash
ssh root@192.168.15.4 "
  # 1. FC host status
  cat /sys/class/fc_host/host7/port_state
  cat /sys/class/fc_host/host8/port_state

  # 2. Tentar LIP reset
  echo 1 > /sys/class/fc_host/host7/issue_lip
  sleep 5
  sg_inq /dev/sg3

  # 3. Verificar driver FC:
  lsmod | grep qla
  dmesg | tail -50 | grep -iE 'fc|host7|qla|ltfs'

  # 4. Reload módulo (último recurso)
  rmmod qla2xxx && modprobe qla2xxx
  sleep 10
  sg_inq /dev/sg3
"
```

> **Nota:** sg5 é o drive secundário (lto6b); se sg3 não responde mas sg5 sim, o problema é isolado ao drive primário.

---

## Ejeção de fita (quando necessário)

```bash
ssh root@192.168.15.4 "
  # Verificar PREVENT flag:
  sg_logs /dev/sg3 -p 0x15 | grep -i prevent   # apenas informativo

  # Permitir remoção + ejetar:
  sg_raw /dev/sg3 1e 00 00 00 00 00   # ALLOW MEDIUM REMOVAL
  sg_start --eject /dev/sg3
  # alternativa: mt -f /dev/nst0 offline
"
```

---

## Erros conhecidos (não críticos)

| Mensagem | Causa | Ação |
|----------|-------|------|
| `MODESELECT -20500` | Parâmetro não suportado pelo drive HP neste contexto; mensagem cosmética, não afeta operação | Ignorar |
| `MODESENSE -20501 Invalid Field in CDB` | Comando MODE SENSE com page code não suportado pelo firmware `J5SW`; LTFS continua montando normalmente | Ignorar — ver nota abaixo |
| `LOAD_UNLOAD returns -20601` | Load durante power-on transitório; drive finaliza o load normalmente | Ignorar |
| `TEST_UNIT_READY returns -20210` | Drive em estado Not-Ready temporário ao iniciar; LTFS aguarda e retenta | Ignorar |
| `Could not reserve device` | Outro processo com o device | `pkill -9 ltfs && sleep 5` |
| `sense 000019` no boot | TUR loop infinito antes do ltfs | Causado por timing; wrapper atual tem wait_stable_fc corrigido |
| `Traceback ltfs_index_export.py:168` | Hook de unmount tenta exportar índice com drive já desmontado; `nst0l` (SCSI tape non-rewind lo-density) é inválido após SIGKILL do ltfs | Ver seção "Bug: ltfs_index_export.py após SIGKILL" |

> **Nota MODESENSE -20501**: Confirmado nos diagnósticos de 2026-04-22. O firmware HP Ultrium 6 `J5SW` não suporta os page codes que o driver `sg-ibmtape` tenta via SCSI opcode `0x5a` / `0x1a`. O LTFS registra a falha, ignora e prossegue com os valores padrão — volume monta com sucesso na sequência imediata. Não é preciso intervir.

---

## Bug: ltfs_index_export.py após SIGKILL

**Sintoma** (journalctl): `Export falhou (rc=1): ... nst: /dev/nst0l … Incorrect block size`

**Causa**: O hook `ltfs_post_mount_hook.py` dispara `ltfs_index_export.py` no `ExecStopPost=`. Quando o systemd manda SIGKILL no `ltfs` (KillMode=mixed), a fita pode estar em estado inconsistente — o comando `mt` seguinte falha com `Incorrect block size`. O script não verifica se o drive está operacional antes de tentar o export SCSI.

**Fix recomendado** — adicionar guard no início do export:

```python
# No ltfs_index_export.py, antes de extract_index_from_partition0():
import subprocess, sys
result = subprocess.run(["mt", "-f", nst, "status"], capture_output=True, timeout=10)
if result.returncode != 0:
    logger.warning("Drive not ready after stop, skipping export: %s", result.stderr.decode())
    sys.exit(0)  # exit 0 = não falhar o hook
```

**Workaround atual**: O hook termina com `rc=1` mas o evento é registrado e o serviço não falha — impacto operacional zero.

---

## Diagnóstico SCSI completo (2026-04-22)

Drive primário: HP Ultrium 6-SCSI, FW `J5SW`, serial `HUJ5485704` (sg3)  
Drive secundário: sg5 (formato/serial não registrado)
HBA: QLogic QLE2562 8Gb FC (qla2xxx), firmware `8.08.207 (90d5)`

**sg_inq VPD (Device ID)**:
- LU WWN: `0x50014380353e592a`
- Port WWN: `0x50014380353e5929`

**sg_logs Device Statistics**:
- Lifetime loads: 10351 | Lifetime POH: 56831h
- Head motion hours: 4651h
- Hard write errors: 0 ✅
- Hard read errors: 12 ⚠️ (não crítico para LTO-6 com 10k loads)
- TapeAlert flags: todos `0` ✅ (nenhum alerta ativo)
- Temperatura atual: 40°C ✅

**Conclusão**: drive saudável, sem alertas, sem erros de escrita. Os erros MODESENSE/MODESELECT são limitações do firmware `J5SW` com o driver IBM — não indicam falha de hardware.

**Verificação rápida de saúde** (executar com LTFS parado):
```bash
ssh root@192.168.15.4 "
  systemctl stop ltfs-lto6.service
  sg_logs -a /dev/sg3 2>/dev/null | grep -E 'Hard.*error|TapeAlert|Temperature'
  systemctl start ltfs-lto6.service
  systemctl start ltfs-nfs-export.service
"
```

---

## Script de reativação automática

```bash
# Copiar para o NAS e executar:
scp scripts/nas_ltfs_nextcloud_reactivate.sh root@192.168.15.4:/tmp/
ssh root@192.168.15.4 bash /tmp/nas_ltfs_nextcloud_reactivate.sh
```

Ou executar remotamente:

```bash
sshpass -p 'Rpa_four_all!' ssh root@192.168.15.4 \
  'bash /workspace/eddie-auto-dev/scripts/nas_ltfs_nextcloud_reactivate.sh'
```

---

## Estado esperado (tudo OK)

```bash
ssh root@192.168.15.4 "
  systemctl is-active ltfs-lto6.service       # active
  systemctl is-active ltfs-nfs-export.service # active (exited)
  mount | grep ltfs                            # sg3→lto6 e sg5→lto6b
  ls /mnt/tape/lto6/.ltfs-ready               # ready-file presente
  exportfs -v                                  # /mnt/tape/lto6 → 192.168.15.0/24
  df -h /mnt/tape/lto6 /mnt/tape/lto6b        # ~2.3T cada
"
```

---

## Incidente 2026-06-28 — EOD missing transiente (SG1R26)

**Sintoma:** `ltfs-lto6.service` falhou às 22:08 de 2026-06-26 com:
```
LTFS17146E EOD of DP(1) is missing. A deep recovery operation is required.
```

**Causa:** Parada abrupta do drive deixou o estado do EOD inconsistente na memória do drive, sem corrupção real da fita. O erro se repetiu em 3 tentativas consecutivas de restart.

**Recovery executado:**
1. `--deep-recovery` via orchestrator na NAS como root
2. ltfsck reportou: `LTFS17141I Both EODs are detected. A deep recovery operation is unnecessary.`
3. Volume íntegro: `LTFS16022I Volume is consistent.`
4. `--orchestrated-mount` montou com sucesso
5. `systemctl reset-failed && start ltfs-lto6.service`
6. `systemctl start ltfs-nfs-export.service`

**Lição:** EOD missing pode ser transiente. Sempre tentar `--deep-recovery` antes de qualquer passo destrutivo. A operação levou < 1 minuto neste caso.
