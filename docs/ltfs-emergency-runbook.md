# Runbook: LTFS Emergência — HP LTO-6 no NAS (192.168.15.4)

> **Versão:** 2026-04-18 · Lições aprendidas do incidente LOCATE -20301

---

## Acesso ao NAS

```bash
sshpass -p 'Rpa_four_all!' ssh root@192.168.15.4
```

---

## Nível 1 — Verificação rápida (2 min)

```bash
# LTFS ativo?
systemctl is-active ltfs-lto6

# Mount points:
findmnt /mnt/tape/lto6
findmnt /run/ltfs-export/lto6
findmnt /srv/nextcloud/external/LTO

# Espaço:
df -h /mnt/tape/lto6
```

Se tudo OK → encerrar. Se não:

---

## Nível 2 — Diagnóstico (5 min)

```bash
# 1. Drive SCSI responde?
sg_inq /dev/sg0

# Se sg_inq travar/falhar: reset LIP do FC
echo "1" > /sys/class/fc_host/host7/issue_lip && sleep 5

# 2. FC Online?
cat /sys/class/fc_host/host7/port_state    # esperado: Online

# 3. Fita carregada?
mt -f /dev/nst0 status | head -8           # deve ter BOT e ONLINE

# 4. TapeAlert (problema de mídia)?
sg_logs /dev/sg0 -p 0x2e | grep ": 1"     # flags setados = problema físico

# 5. Partição de dados vazia ou com dados?
sg_logs /dev/sg0 -p 0x31 | grep -E "Main.*remaining|Main.*maximum"
# Se remaining == maximum → fita VAZIA → pode reformatar sem perda!
# Se remaining < maximum → há dados escritos → cuidado antes de reformatar
```

---

## Nível 3 — Recuperação LTFS corrompido

### Caso: LTFS não monta, ltfs log mostra erros de índice

```bash
systemctl stop ltfs-lto6
pkill -9 ltfs || true
sleep 3

# Tentar recuperação suave:
ltfsck -f /dev/sg0

# Se ltfsck -f falhar com LOCATE -20301:
#  ↳ VÁ PARA O NÍVEL 4
```

### Caso: LTFS trava ao montar (não responde)

```bash
# Force unmount
fusermount -uz /mnt/tape/lto6 || umount -l /mnt/tape/lto6
pkill -9 ltfs

# Aguardar drive ficar em estado READY
sg_turs -n 3 /dev/sg0   # 3 retries de TUR

# Restart via systemd
systemctl reset-failed ltfs-lto6
systemctl start ltfs-lto6
journalctl -u ltfs-lto6 -f   # monitorar
```

---

## Nível 4 — LOCATE -20301 (BOT markers corrompidos)

> **⚠️ Este é o caminho MAIS RÁPIDO quando você vê `-20301` em qualquer ltfsck ou mount attempt.**

### Confirmar antes de reformatar:

```bash
sg_logs /dev/sg0 -p 0x31 | grep -E "Main.*remaining|Main.*maximum"
```

- Se `remaining == maximum` (ex: ambos `36750 MiB`) → **fita está vazia** → reformatar sem risco.
- Se `remaining < maximum` → há dados → confirmar com usuário antes de reformatar.

### Reformatação (mkltfs --force):

```bash
# 1. Parar tudo
systemctl stop ltfs-lto6
pkill -9 ltfs || true
sleep 3

# 2. Rewind
mt -f /dev/nst0 rewind

# 3. Formatar (EXATAMENTE 6 caracteres no serial — truncar se necessário)
# Serial HUJ5485716 → usar HUJ548
mkltfs --force \
  --device=/dev/sg0 \
  --tape-serial=HUJ548 \
  --volume-name="LTO6-NAS-$(date +%Y%m%d)"

# Duração: ~5-10 min. Saída esperada:
# "LTFS volume successfully created"

# 4. Reiniciar serviço
systemctl reset-failed ltfs-lto6
systemctl start ltfs-lto6

# 5. Aguardar mount (~30-120s)
watch -n5 systemctl is-active ltfs-lto6
```

### Após mount bem-sucedido, restaurar bind mounts:

```bash
# Verificar se bind mounts foram recriados pelo wrapper:
findmnt /run/ltfs-export/lto6
findmnt /srv/nextcloud/external/LTO

# Se não foram (ex: foram adicionados manualmente depois do wrapper atual):
mount --bind /mnt/tape/lto6 /run/ltfs-export/lto6
mount --bind /run/ltfs-export/lto6 /srv/nextcloud/external/LTO

# Teste de escrita Nextcloud:
touch /srv/nextcloud/external/LTO/ltfs_write_test_$(date +%s).txt && echo "WRITE OK"
```

---

## Nível 5 — Drive não responde ao sg_inq (HBA/FC)

```bash
# 1. FC host status
cat /sys/class/fc_host/host7/port_state
cat /sys/class/fc_host/host7/speed

# 2. Tentar LIP reset
echo "1" > /sys/class/fc_host/host7/issue_lip
sleep 5
sg_inq /dev/sg0

# 3. Se persistir: verificar se fita está carregada e drive ligado
# 4. Verificar driver FC:
lsmod | grep qla
dmesg | tail -50 | grep -iE "fc|host7|qla|ltfs"

# 5. Reload módulo (último recurso)
rmmod qla2xxx && modprobe qla2xxx
sleep 10
sg_inq /dev/sg0
```

---

## Ejeção de fita (quando necessário)

```bash
# Verificar PREVENT flag:
sg_logs /dev/sg0 -p 0x15 | grep -i prevent   # apenas informativo

# Permitir remoção + ejetar:
sg_raw /dev/sg0 1e 00 00 00 00 00   # ALLOW MEDIUM REMOVAL
sg_start --eject /dev/sg0
# alternativa: mt -f /dev/st0 offline
```

---

## Erros conhecidos (não críticos)

| Mensagem | Causa | Ação |
|----------|-------|------|
| `MODESELECT -20500` | Driver HP, não afeta operação | Ignorar |
| `Could not reserve device` | Outro processo com o device | `pkill -9 ltfs && sleep 5` |
| `sense 000019` no boot | TUR loop infinito antes do ltfs | Causado por timing; wrapper atual tem wait_stable_fc corrigido |

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

```
systemctl is-active ltfs-lto6      → active
findmnt /mnt/tape/lto6             → ltfs on /mnt/tape/lto6
findmnt /run/ltfs-export/lto6      → /mnt/tape/lto6 on /run/ltfs-export/lto6
findmnt /srv/nextcloud/external/LTO → /run/ltfs-export/lto6 on /srv/nextcloud/external/LTO
df -h /mnt/tape/lto6               → ~2.3T disponível (fita nova/vazia)
```
