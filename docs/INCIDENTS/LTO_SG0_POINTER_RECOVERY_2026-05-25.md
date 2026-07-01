# Incidente — Recuperação por ponteiro LTFS no sg0 — 2026-05-25

## Resumo

Em 2026-05-25 a fita principal `sg0` entrou em recuperação após uma sequência
de stop/mount concorrente. O LTFS encontrou blocos extras e índice inconsistente:

```text
LTFS11257I No index found in the index partition.
LTFS11220E Medium check failed: extra blocks detected. Run ltfsck.
```

O volume foi recuperado com `ltfsck -f /dev/sg0`. A última persistência válida
confirmada foi:

```text
Volume mounted successfully. NO_BARCODE : Gen = 343 / (a, 5) -> (b, 1232686) / HUJ5485716.
LTFS16022I Volume is consistent.
```

Depois da remount e retomada controlada do flush, o LTFS escreveu novo índice:

```text
Wrote index of NO_BARCODE (Gen = 344, Part = b, Pos = 1234423, HUJ5485716).
```

## Causa raiz

Foram encontrados quatro pontos de fragilidade:

1. `ltfs-lto6.service` usava `TimeoutStopSec=120`, `KillMode=mixed` e permitia
   SIGKILL. Isso podia matar o LTFS enquanto ele ainda escrevia ou fechava o
   índice.
2. O wrapper de mount seguia adiante mesmo com `/dev/sg0` ocupado por `ltfsck`,
   `ltfs` ou processo de flush anterior.
3. `ltfs-cache-flush.service.d/70-rearm-timer-on-exit.conf` rearmava o timer a
   partir de `ExecStopPost`. Durante recuperação isso brigava com a pausa
   operacional e deixava `systemctl stop` preso em `stop-post`.
4. O modo `--cursor-recover` existia, mas só executava `ltfsck` e reportava
   listas. Ele não fazia rollback real para um rollback point LTFS quando o
   índice corrente não era montável.

## Correções implementadas

### Serviço LTFS

`systemd/ltfs-lto6.service`:

- `TimeoutStopSec=900`
- `KillMode=process`
- `SendSIGKILL=no`
- `ExecStop=/usr/bin/python3 /usr/local/tools/ltfs_recovery.py --orchestrated-stop`

Objetivo: dar tempo para o LTFS terminar sync/flush de índice sem SIGKILL.

### Wrapper de start

`tools/ltfs-lto6-start`:

- espera holders de `/dev/sg0` e `/dev/nst0`
- aborta se o device continuar ocupado após `LTFS_DEVICE_BUSY_TIMEOUT_SECONDS`
- não monta por cima de `ltfsck` ou outro LTFS ainda segurando o drive

### Wrapper de stop

`tools/ltfs-lto6-stop`:

- stop gracioso com `LTFS_STOP_GRACE_SECONDS`
- SIGKILL só se `LTFS_STOP_ALLOW_SIGKILL=true`
- evita transformar um unmount lento em corrupção de índice
- bloqueia unmount se houver writer ativo ou cursor com progresso no device
  atual, salvo override explícito

### Suspensão de serviços interferentes

`tools/ltfs_recovery.py` agora suspende e restaura serviços/timers com estado:

- captura `systemctl is-active` e `systemctl is-enabled`
- para serviços/timers interferentes
- mascara timers em runtime durante recovery
- grava estado em `LTFS_SUSPEND_STATE_FILE`
- ao final saudável, desmascara e religa apenas units que estavam ativas antes

Variáveis:

```bash
LTFS_CONFLICT_SERVICES=tape-safe-eject.service,ltfs-idle-unmount.timer,ltfs-idle-unmount.service,ltfs-cache-flush.timer,ltfs-cache-flush.service,ltfs-udev-mount.service
LTFS_BACKGROUND_UNITS=ltfs-cache-flush.timer,ltfs-cache-flush.service,ltfs-idle-unmount.timer,ltfs-idle-unmount.service,lto6-metrics-export.timer,lto6-metrics-export.service
LTFS_SUSPEND_STATE_FILE=/run/ltfs-recovery/suspended-units.json
LTFS_SUSPEND_MASK_TIMERS=true
```

### Remoção do rearm via ExecStopPost

Removido:

```text
systemd/ltfs-cache-flush.service.d/70-rearm-timer-on-exit.conf
```

Motivo: recovery precisa conseguir parar e manter timers parados. Rearmar o
timer de dentro do próprio serviço de flush quebra essa garantia. O retorno dos
timers agora pertence ao orquestrador, depois de `--check` saudável.

### Recovery real a partir do ponteiro

`--cursor-recover` agora tem fallback real:

1. tenta `ltfsck -f`
2. se falhar, lista rollback points com `ltfsck -l -m`
3. seleciona a geração mais nova anterior ou igual ao timestamp do cursor
4. executa `ltfsck -g <generation> -r -j`
5. separa arquivos recuperados e arquivos para re-fila com base no timestamp do
   rollback point

Limitação conhecida: no sg0 atual `last_block` do cursor aparece como `null`,
porque `mt tell` não retorna bloco útil durante LTFS/FUSE. Por isso o ponteiro
confiável para rollback é a geração LTFS e o timestamp de persistência, não o
bloco físico bruto.

### Cursor durante flush

`tools/tape_manager.py`:

- abre cursor no começo de `flush`
- atualiza cursor por arquivo copiado e sincronizado
- fecha cursor apenas quando o flush termina sem falhas e sem interrupção
- trata SIGTERM/SIGINT parando entre arquivos, não no meio de uma cópia

`tools/ltfs_recovery.py`:

- `cursor_update` reabre defensivamente cursor que estava `clean`
- `cursor_close/status` retornam resumo, sem despejar milhares de arquivos no
  journal
- `--check` passa a falhar com `cursor_recovery_required=true` quando há cursor
  aberto no device atual e o LTFS está desmontado fora da janela
- `--diagnose` classifica esse estado como `open_cursor_requires_recovery`
- `--self-heal` aceita `cursor_recover` como ação automática e seleciona o
  cursor aberto mais recente do device atual, ignorando cursores antigos de
  outros drives
- `--orchestrated-stop` executa preflight rígido antes de parar serviços:
  `ltfs-cache-flush.service`/backup/drain ativos ou cursor com progresso
  bloqueiam o stop. A barreira também existe no wrapper `ltfs-lto6-stop`.

## Procedimento operacional atualizado

### Congelar recuperação

```bash
ssh homelab@192.168.15.2 "ssh nas '
  systemctl mask --runtime ltfs-cache-flush.timer lto6-selfheal.timer ltfs-idle-unmount.timer
  systemctl stop ltfs-cache-flush.service ltfs-cache-flush.timer lto6-selfheal.service lto6-selfheal.timer ltfs-idle-unmount.service ltfs-idle-unmount.timer || true
'"
```

Não matar `ltfs` ou `ltfsck` se eles estiverem fazendo recovery. Validar holders:

```bash
ssh homelab@192.168.15.2 "ssh nas 'lsof /dev/sg0 /dev/st0 /dev/nst0 2>/dev/null || true'"
```

### Recuperar pela última persistência válida

Preferencial:

```bash
ssh homelab@192.168.15.2 "ssh nas 'python3 /usr/local/tools/ltfs_recovery.py --cursor-recover --volser UNKNOWN'"
```

Se o cursor ainda não existir ou o erro for apenas índice inconsistente:

```bash
ssh homelab@192.168.15.2 "ssh nas 'ltfsck -f /dev/sg0'"
```

### Validar antes de retomar timers

```bash
ssh homelab@192.168.15.2 "ssh nas '
  findmnt /mnt/tape/lto6
  python3 /usr/local/tools/ltfs_recovery.py --check
  python3 /usr/local/tools/ltfs_recovery.py --cursor-status --volser UNKNOWN
'"
```

Critério mínimo:

- mount ativo em `/mnt/tape/lto6`
- `--check` retorna `Catálogo LTFS acessível`
- cursor está `clean` se não houver flush ativo, ou `in_progress` se o flush
  estiver realmente copiando arquivos

### Retomar timers

```bash
ssh homelab@192.168.15.2 "ssh nas '
  systemctl unmask ltfs-cache-flush.timer lto6-selfheal.timer ltfs-idle-unmount.timer
  systemctl start ltfs-cache-flush.timer lto6-selfheal.timer ltfs-idle-unmount.timer
'"
```

## Validação executada em 2026-05-25

No NAS:

- `/usr/local/tools/ltfs_recovery.py --help` OK
- `/usr/local/bin/tape-manager --help` OK
- `systemd-analyze verify` para units LTFS OK
- `findmnt /mnt/tape/lto6` OK
- `ltfs_recovery.py --check` OK
- 31.945 caminhos do cursor inicial conferidos no catálogo recuperado sem
  faltantes
- cursor passou de `clean` para `in_progress` quando o flush retomou
- novo índice periódico `Gen = 344` escrito após recuperação

No repositório:

```bash
PYTHONPATH=. pytest -q tests/test_ltfs_recovery.py tests/test_ltfs_orchestrator_exclusive.py tests/test_tape_orchestrator.py
python3 -m py_compile tools/ltfs_recovery.py tools/tape_manager.py
bash -n tools/ltfs-lto6-start tools/ltfs-lto6-stop
git diff --check -- tools/ltfs_recovery.py tools/tape_manager.py tools/ltfs-lto6-start tools/ltfs-lto6-stop systemd/ltfs-lto6.service .github/workflows/deploy-ltfs-recovery-runtime.yml tests/test_ltfs_recovery.py tests/test_ltfs_orchestrator_exclusive.py
```

## Correção adicional: mountpoints para buffer

Durante a retomada do flush foi encontrada uma classe separada de risco:
mountpoints e shares de cliente ainda podiam alcançar o LTFS bruto. Isso
permitiria escrita, leitura pesada ou limpeza fora do `tape-manager`.

Alterações aplicadas no NAS:

- `/etc/samba/ltfs-lto6.conf`: `LTO6`, `LTO6_CACHE` e `LTO6_VIEW` apontam para
  `/var/spool/lto6-cache`.
- `/etc/samba/ltfs-lto6.conf`: `LTO6_SG1` aponta para
  `/var/spool/lto6-cache-sg1`.
- `/etc/exports`: export direto de `/mnt/tape/lto6` foi comentado; o export
  ativo é `/var/spool/lto6-cache`.
- `/usr/local/sbin/ltfs-share-guard`: caminhos `/var/spool/lto6-cache*` são
  permitidos como staging em disco.

Alterações aplicadas no homelab:

- `/etc/fstab`: mount CIFS direto `//192.168.15.4/LTO6 /mnt/lto6` foi
  desativado.
- `/mnt/lto6` e `/mnt/tape_sg0` passam a resolver para buffer/mergerfs.
- `/mnt/tape_sg1` remonta `//192.168.15.4/LTO6_SG1`, agora servido pelo buffer
  do NAS.
- `tape-retention-30d.timer` foi desabilitado para evitar limpeza por path de
  mount até existir retenção catalog-aware.

Validação final:

```text
NAS testparm:
  LTO6      -> /var/spool/lto6-cache
  LTO6_SG1  -> /var/spool/lto6-cache-sg1
  LTO6_VIEW -> /var/spool/lto6-cache

NAS exportfs:
  /var/spool/lto6-cache

Homelab findmnt:
  /mnt/lto6           -> mergerfs[/lto6-cache]
  /mnt/tape_sg0       -> mergerfs[/lto6-cache]
  /mnt/tape_sg1       -> //192.168.15.4/LTO6_SG1
  /mnt/lto6-cache-nas -> //192.168.15.4/LTO6_CACHE
```

## Critérios de parada

Parar automação e escalar manualmente se:

- `ltfsck -f` e `--cursor-recover` falharem
- `ltfsck -l -m` não listar rollback points
- o drive apresentar erros SCSI persistentes (`READ`, `LOCATE`, `TEST_UNIT_READY`)
  depois de reset e nova tentativa
- o catálogo monta mas leituras simples travam
- `lsof` mostra processo inesperado segurando `/dev/sg0` durante recovery

## Arquivos alterados

- `tools/ltfs_recovery.py`
- `tools/tape_manager.py`
- `tools/ltfs-lto6-start`
- `tools/ltfs-lto6-stop`
- `systemd/ltfs-lto6.service`
- `.github/workflows/deploy-ltfs-recovery-runtime.yml`
- `tests/test_ltfs_recovery.py`
- `tests/test_ltfs_orchestrator_exclusive.py`
- `docs/ltfs-emergency-runbook.md`
- `docs/tape-archive-paths.md`
