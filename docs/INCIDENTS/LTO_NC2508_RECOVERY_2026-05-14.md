# Incidente — Recuperação da Fita LTO NC2508L — 2026-05-14

> Perda de acesso à fita NC2508L por label VOL1 truncada após SIGKILL; diagnóstico de dados; reformatação e restauração do pipeline.

---

## Resumo Executivo

Em 2026-05-14, a fita HP LTO-6 NC2508L tornou-se inacessível após um SIGKILL no processo `ltfs` durante a operação de stop do serviço. A label ANSI VOL1 da partição 1 ficou com 54 bytes (em vez de 80), tornando o LTFS incapaz de montar a fita.

Uma tentativa anterior de auto-recuperação gravou uma nova VOL1 mas posicionou o EOD (End-of-Data) no bloco 1 da partição de dados, destruindo o acesso a 291.416 blocos de dados gravados.

**Resultado:** Todos os 632.790 arquivos que estavam na fita eram **cópias de backup** geradas pelo script `lto6-drain-backups` via rsync — os originais estavam intactos no RAID1 do homelab (`/mnt/raid1/backups/`). **Zero perda de dados primários.**

A fita foi reformatada com `mkltfs` e os backups estão sendo restaurados via drain.

---

## Linha do Tempo

| Hora | Evento |
|------|--------|
| ~13:27 | SIGKILL no processo ltfs durante `ExecStop` de `ltfs-lto6.service` |
| ~13:27 | VOL1 truncada para 54 bytes; tentativa de auto-recuperação destrói EOD |
| 13:xx | `ltfsck -z` confirma: EOD em bloco 1, 291.416 blocos irrecuperáveis |
| 13:xx | Análise confirma: dados na fita eram APENAS backups rsync do RAID1 |
| ~13:50 | `mkltfs --force -s NC2508` reformata a fita (UUID `2246ad24-23a4-4526-afea-8fb493bf39d3`, 2524 GB) |
| ~14:xx | LTFS montado manualmente; dir `/mnt/tape/lto6/backups` criado |
| ~15:00 | Problema L2 homelab ↔ NAS diagnosticado: ARP stale no NAS |
| ~15:42 | Reboot NAS resolve ARP; `ltfs-lto6.service` sobe automaticamente e corretamente |
| 15:51 | `lto6-drain-backups` iniciado manualmente: restaurando snapshots RAID1 → fita |

---

## Causa Raiz

### 1. SIGKILL durante ExecStop

O `ExecStop` de `ltfs-lto6.service` chama `/usr/local/tools/ltfs_recovery.py --orchestrated-stop`, que detecta o processo `ltfs` com device `sg0` aberto e retorna `"Operação 'stop' bloqueada por concorrência"` com código 1.

O systemd, ao receber falha no ExecStop, envia `SIGKILL` diretamente ao processo `ltfs` (PID 1867749). O SIGKILL ocorre no meio de uma operação de escrita na partição 1 da fita, truncando a label VOL1 para 54 bytes.

### 2. EOD destruído pela recuperação automática

O script de recuperação tentou reescrever a label VOL1 (80 bytes), mas ao fazer isso posicionou o EOD no bloco imediatamente posterior (bloco ~1-2). O firmware HP Ultrium 6 (`J5SW`) rejeita qualquer `LOCATE16` para além do EOD com `Blank Check` (sense key 0x08), tornando os 291.416 blocos de dados irrecuperáveis por qualquer ferramenta SCSI.

### 3. Isolamento L2 no switch (homelab ↔ NAS)

O homelab (192.168.15.2) e NAS (192.168.15.4) não conseguiam se comunicar diretamente — ARP stale no NAS bloqueava a resolução L2. O reboot do NAS limpou o estado e restaurou a conectividade.

---

## Dados na Fita — Análise

| Item | Valor |
|------|-------|
| Arquivos na fita (antes de reformatar) | 632.790 |
| Tipo de dados | Cópias rsync de `rpa4all-snapshot-*` |
| Origem dos dados | `lto6-drain-backups` (homelab RAID1 → fita via CIFS) |
| Arquivos primários intactos? | **Sim** — em `/mnt/raid1/backups/` no homelab |
| Dados Nextcloud de usuário perdidos? | **Não** — Nextcloud data está em `nc-nas-data` (NFS) |
| Perda de dados primários | **Zero** |

Os 632.790 arquivos eram snapshots de sistema do homelab (`rpa4all-snapshot-20260501T030006Z` = 59 GB, `rpa4all-snapshot-20260502T100642Z` = 99 GB) transferidos pelo timer `lto6-drain-backups` em execuções anteriores.

---

## Ações Executadas

### 1. Diagnóstico da fita

```bash
# Na NAS
sg_raw /dev/sg0 92 02 00 01 00 00 00 00 00 01 00 00  # LOCATE16 → partition 1, block 1
# Resposta: "End-of-data detected" → confirma EOD destruído

# Análise da VOL1 truncada
sg_raw -i 54 /dev/sg0 01 00 00 00 36 00  # READ 54 bytes da P1
# Resultado: "VOL1NC2508          " — 54 bytes, não 80
```

### 2. Reformatação

```bash
# 1. Parar LTFS
systemctl stop ltfs-lto6
pkill -9 ltfs || true
mt -f /dev/nst0 rewind

# 2. Reformatar (6 chars no serial — NC2508L truncado para NC2508)
/usr/local/ltfs-patched/bin/mkltfs \
  -d /dev/sg0 \
  -s NC2508 \
  -n NEXTCLOUD-LTO6 \
  -b 524288 \
  --force

# Resultado: UUID 2246ad24-23a4-4526-afea-8fb493bf39d3, 2524 GB
```

### 3. Mount manual e restauração do bind

```bash
# Montar LTFS
nohup /usr/local/ltfs-patched/bin/ltfs /mnt/tape/lto6 \
  -o devname=/dev/sg0 \
  -o work_directory=/var/lib/ltfs/work \
  -o nonempty \
  -o scsi_append_only_mode=off &

# Bind mount para Samba
mount --bind /mnt/tape/lto6 /run/ltfs-export/lto6
mkdir -p /mnt/tape/lto6/backups
```

### 4. Reboot NAS — resolução do ARP L2

O homelab não conseguia alcançar o NAS (ARP `INCOMPLETE`) mesmo com entradas ARP estáticas manuais — isolamento de porta no switch impedia tráfego direto.

O reboot do NAS limpou o estado ARP stale. Após o reboot, `ltfs-lto6.service` subiu automaticamente e corretamente (status `active (exited)`, todos os ExecStartPost OK).

### 5. Restauração dos backups (drain em andamento)

```bash
# No homelab — iniciado em 2026-05-14T15:51
nohup sudo /usr/local/sbin/lto6-drain-backups > /tmp/lto6-drain-*.log 2>&1 &

# Transferindo:
# - rpa4all-snapshot-20260501T030006Z (59 GB)
# - rpa4all-snapshot-20260502T100642Z (99 GB)
# Total: ~158 GB para /mnt/lto6-smb-proof/backups/ → fita via CIFS
```

---

## Estado do Pipeline Pós-Recuperação

| Componente | Status |
|---|---|
| `ltfs-lto6.service` | active (exited) — montagem automática no boot |
| LTFS em `/mnt/tape/lto6` | montado, 2.3T disponíveis |
| Bind `/run/ltfs-export/lto6` | OK |
| Samba LTO6 / LTO6_CACHE | ativos, path `/run/ltfs-export/lto6` |
| `lto6-drain-backups` (manual) | **rodando** — restaurando 158 GB |
| `lto6-drain-backups.timer` | active, próximo disparo 2026-05-15 04:00 |
| `lto6-smb-proof-selfheal.timer` | active, a cada 2 min |
| `ltfs-cache-flush.timer` (homelab) | active, a cada 5 min |
| `ltfs-cache-flush.timer` (NAS) | active |
| `lto6-selfheal.timer` (NAS) | active |
| `tape-component-quality-exporter` | active, `overall_score=98.7` |
| Nextcloud container | Up 42h, external LTO acessível |
| Conectividade homelab ↔ NAS | OK (0% packet loss) |

---

## Fix Aplicado — `orchestrated_stop()` com fusermount pré-passo

**Commit:** `fix(ltfs): fusermount gracioso antes de verificar holders no orchestrated_stop`

**Arquivo:** `tools/ltfs_recovery.py` (workspace) + `/usr/local/tools/ltfs_recovery.py` (NAS)

### Diagnóstico da causa no código

`orchestrated_stop()` chamava diretamente `_run_exclusive_operation("stop", ...)`, que executa:
1. `_list_tape_holders()` — lista processos com `/dev/sg0` aberto via `lsof`
2. `_filter_unexpected_holders()` — o processo `ltfs` FUSE aparece como "unexpected holder" (não é filho do orchestrador)
3. Retorna `success=false` com `"Operação 'stop' bloqueada por concorrência"` → exit 1
4. systemd recebe falha no ExecStop → envia SIGKILL direto ao processo `ltfs`

O problema: o `ltfs` FUSE **mantém `/dev/sg0` aberto enquanto está montado** — é um comportamento esperado. O holder check não deve ocorrer antes de desmontá-lo.

### Fix implementado

```python
def orchestrated_stop() -> Dict[str, Any]:
    """Desmonta LTFS de forma orquestrada e exclusiva."""
    # Pré-passo: fusermount gracioso ANTES de verificar holders.
    # O processo ltfs FUSE mantém /dev/sg0 aberto enquanto montado.
    # Verificar holders primeiro faz o ltfs aparecer como "unexpected holder",
    # bloqueando o stop e forçando o systemd a enviar SIGKILL na fita — causa
    # raiz do incidente NC2508L 2026-05-14 (VOL1 truncada, EOD destruído).
    mp = str(LTFS_MOUNT_POINT)
    if _run_command(["mountpoint", "-q", mp]).returncode == 0:
        LOGGER.info("orchestrated_stop: fusermount gracioso em %s", mp)
        r = _run_command(["fusermount", "-u", mp])
        if r.returncode != 0:
            LOGGER.warning("fusermount -u falhou (rc=%d), tentando -uz (lazy)", r.returncode)
            _run_command(["fusermount", "-u", "-z", mp])
        # Aguardar o processo ltfs liberar sg0 (até 15 s)
        for _ in range(15):
            if not _list_tape_holders():
                break
            time_module.sleep(1)
    return _run_exclusive_operation("stop", ["/usr/local/sbin/ltfs-lto6-stop"])
```

### Fluxo pós-fix

```
ExecStop= ltfs_recovery.py --orchestrated-stop
  └─ orchestrated_stop()
       ├─ mountpoint -q /mnt/tape/lto6 → montado
       ├─ fusermount -u /mnt/tape/lto6  ← NOVO: desmonta FUSE graciosamente
       │    └─ ltfs FUSE recebe sinal → flush → fecha sg0 → encerra
       ├─ aguarda até 15s para sg0 ser liberado
       └─ _run_exclusive_operation("stop", ...)
            ├─ _list_tape_holders() → [] (sg0 já livre)
            └─ ltfs-lto6-stop → exit 0  ✓
```

### Deploy

```bash
# NAS — backup automático criado em:
/usr/local/tools/ltfs_recovery.py.bak_20260514_160539

# Verificação pós-deploy:
python3 -c 'import ast; ast.parse(open("/usr/local/tools/ltfs_recovery.py").read()); print("OK")'
# → syntax OK
```

---

## Lições Aprendidas

1. **SIGKILL no processo ltfs pode truncar a label VOL1** — o processo `ltfs` (FUSE) escreve metadados na fita assincronamente; um SIGKILL abrupto pode corromper estruturas críticas.

2. **Tentativa de reescrever VOL1 destrói EOD** — qualquer escrita na partição de dados move o EOD; blocos anteriores ficam irrecuperáveis por SCSI.

3. **Dados na fita devem ser identificados antes de reformatar** — verificar sempre se os dados são primários ou cópias de backup. Neste caso, eram APENAS cópias rsync.

4. **`mkltfs` exige serial de exatamente 6 caracteres** — `NC2508L` (7 chars) é rejeitado; usar `NC2508`.

5. **ARP stale em máquinas virtuais/físicas pode persistir indefinidamente** — o reboot é o fix mais confiável para estados ARP corrompidos.

6. **O ExecStop precisa de estratégia de desmontagem graciosa** — `fusermount -uz` antes de verificar processos evita SIGKILLs prematuros na fita.

---

## Arquivos Criados/Modificados Nesta Sessão

| Local | Arquivo | Operação |
|-------|---------|----------|
| NAS `/usr/local/ltfs-patched/bin/` | `ltfs` (original restaurado de `.bak`) | Restaurado do backup |
| NAS `/mnt/tape/lto6/` | Fita reformatada | `mkltfs --force` |
| NAS `/mnt/tape/lto6/backups/` | Diretório criado | `mkdir` |
| Homelab `/tmp/` | `lto6-drain-*.log` | Log do drain em andamento |
