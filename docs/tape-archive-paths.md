# Sistema de Gerenciamento de Fitas LTO-6 — Documentação Técnica

> Última atualização: 2026-05-18
> NAS: `192.168.15.4` (rpa4all-nas-001)
> Acesso: `ssh homelab` → `ssh nas` (ou `ssh homelab "ssh nas '...'"`)

---

## 1. Arquitetura Geral

```
┌──────────────────────────────────────────────────────────┐
│  Dev Machine (TANK)                                      │
│  192.168.15.x / WiFi TANK                                │
│                                                          │
│  /workspace/eddie-auto-dev/tools/                        │
│    ├── tape_manager.py        ← ciclo de vida completo   │
│    ├── tape_orchestrator.py   ← cursor + mount hooks     │
│    ├── ltfs_recovery.py       ← auto-heal + cursor       │
│    └── tape_dual_recovery.py  ← monitor dual progressbar │
└──────────────┬───────────────────────────────────────────┘
               │ SSH (via homelab alias)
               ▼
┌──────────────────────────────────────────────────────────┐
│  Homelab (192.168.15.2)                                  │
│  Relay SSH → NAS                                         │
└──────────────┬───────────────────────────────────────────┘
               │ SSH
               ▼
┌──────────────────────────────────────────────────────────┐
│  NAS (192.168.15.4 — rpa4all-nas-001)                    │
│                                                          │
│  /usr/local/tools/                                       │
│    ├── tape_manager.py        (symlink: /usr/local/bin/tape-manager)
│    ├── tape_orchestrator.py                              │
│    └── ltfs_recovery.py                                  │
│                                                          │
│  HP Ultrium 6-SCSI drives:                               │
│    sg0  [0:0:0:0]  serial HUJ5485716  → /mnt/tape/lto6  │
│    sg2  [7:0:1:0]  serial HUJ548570K  → /mnt/tape/lto6-sg1
│         (enumerado como sg2 após troca do receptor óptico em 2026-05-18)
└──────────────────────────────────────────────────────────┘
```

---

## 2. Drives e Volumes

| Slot | Device SCSI | Tape Device | Serial Drive | Volser Fita | Mountpoint | Capacidade |
|------|------------|-------------|--------------|-------------|------------|------------|
| sg0 | `/dev/sg0` | `/dev/nst0` | HUJ5485716 | **NC2508** | `/mnt/tape/lto6` | 2.3 TB |
| sg1 | `/dev/sg2` | `/dev/nst2` | HUJ548570K | **EVATWG** | `/mnt/tape/lto6-sg1` | 2.3 TB |

> **Nota sg1→sg2**: O drive sg1 foi enumerado como `/dev/sg2` após troca do receptor
> óptico (SFP FC) em 2026-05-18. O env `/etc/default/ltfs-lto6-sg1` já foi atualizado.
> Se o receptor for trocado novamente, rodar `lsscsi -g` para confirmar o mapeamento.

---

## 3. Serviços systemd

### 3.1 ltfs-lto6.service (sg0)

```ini
# /etc/systemd/system/ltfs-lto6.service
[Unit]
Description=LTFS mount for HP LTO-6
After=local-fs.target network.target
Requires=local-fs.target
Conflicts=tape-safe-eject.service ltfs-deep-recovery.service

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=-/etc/default/ltfs-lto6
ExecStart=/usr/bin/python3 /usr/local/tools/ltfs_recovery.py --orchestrated-mount
ExecStop=/usr/bin/python3 /usr/local/tools/ltfs_recovery.py --orchestrated-stop
TimeoutStartSec=480
TimeoutStopSec=120
KillMode=mixed
```

### 3.2 ltfs-lto6-sg1.service (sg1/sg2)

```ini
# /etc/systemd/system/ltfs-lto6-sg1.service
[Unit]
Description=LTFS mount for HP LTO-6 on sg1
After=local-fs.target network.target
Conflicts=tape-safe-eject.service ltfs-deep-recovery.service

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=-/etc/default/ltfs-lto6-sg1
ExecStart=/usr/bin/python3 /usr/local/tools/ltfs_recovery.py --orchestrated-mount
ExecStop=/usr/bin/python3 /usr/local/tools/ltfs_recovery.py --orchestrated-stop
ExecStartPost=/bin/mkdir -p /run/ltfs-export/lto6-sg1
ExecStartPost=/bin/mount --bind /mnt/tape/lto6-sg1 /run/ltfs-export/lto6-sg1
ExecStopPost=-/bin/umount -l /run/ltfs-export/lto6-sg1
ExecStopPost=-/bin/rmdir /run/ltfs-export/lto6-sg1
TimeoutStartSec=480
TimeoutStopSec=120
KillMode=mixed
```

### 3.3 Arquivo de ambiente /etc/default/ltfs-lto6-sg1

```bash
LTFS_SERVICE=ltfs-lto6-sg1.service
LTFS_MOUNT_POINT=/mnt/tape/lto6-sg1
LTFS_WORKDIR=/var/lib/ltfs/work-sg1
LTFS_LOGFILE=/var/log/ltfs-lto6-sg1.log
LTFS_PIDFILE=/run/ltfs-lto6-sg1.pid
LTFS_DEVICE=/dev/sg2
LTFS_TAPE_DEVICE=/dev/nst2
LTO6_SG_DEV=/dev/sg2
LTO6_ST_DEV=/dev/st2
LTO6_NST_DEV=/dev/nst2
LTFS_ORCH_LOCK=/run/lock/ltfs-orchestrator-sg1.lock
LTFS_SELF_HEAL_STATE_FILE=/var/lib/ltfs/self_heal_state_sg1.json
LTFS_CURSOR_DIR=/var/lib/ltfs/cursors
```

---

## 4. Scripts e Utilitários

### 4.1 `tape_manager.py` — Ciclo de vida completo

**Localização NAS**: `/usr/local/tools/tape_manager.py`
**Symlink**: `/usr/local/bin/tape-manager`
**Localização dev**: `tools/tape_manager.py`

```bash
tape-manager start              # monta com retry, recovery e SCSI flush automático
tape-manager flush              # copia CACHE_DIR → TAPE_DIR com cursor por arquivo
tape-manager stop               # fecha cursor + para serviço
tape-manager recover [--deep]   # ltfsck + cursor-recover + remount
tape-manager run                # ciclo completo: start → flush → stop
tape-manager status             # JSON com estado atual
tape-manager start --no-notify  # sem notificações Telegram
```

**Variáveis de ambiente:**

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `LTFS_DEVICE` | `/dev/sg0` | Device SCSI |
| `LTFS_TAPE_DEVICE` | `/dev/nst0` | Device tape |
| `LTFS_MOUNT_POINT` | `/mnt/tape/lto6` | Mountpoint |
| `LTFS_SERVICE` | `ltfs-lto6.service` | Nome do serviço |
| `LTFS_CACHE_DIR` | `/var/spool/lto6-cache` | Diretório de staging |
| `LTFS_ORCH_LOCK` | `/run/lock/ltfs-tape-exclusive.lock` | Lock exclusivo |
| `LTFS_MAX_MOUNT_ATTEMPTS` | `5` | Tentativas de mount |
| `LTFS_MOUNT_COOLDOWN` | `60` | Segundos entre tentativas |
| `LTFS_MEDIUM_WAIT_TIMEOUT` | `120` | Timeout aguardando fita |
| `TG_ENV_FILE` | `/home/homelab/myClaude/.env` | Credenciais Telegram |

**Uso para sg1:**
```bash
LTFS_DEVICE=/dev/sg2 \
LTFS_TAPE_DEVICE=/dev/nst2 \
LTFS_SERVICE=ltfs-lto6-sg1.service \
LTFS_MOUNT_POINT=/mnt/tape/lto6-sg1 \
LTFS_ORCH_LOCK=/run/lock/ltfs-orchestrator-sg1.lock \
tape-manager start
```

**Cenários de recovery implementados:**

| Cenário | Detecção | Ação automática |
|---------|----------|----------------|
| Lock obsoleto (PID morto) | `kill -0 PID` falha | Remove lock, continua |
| Fita não presente | `-20209` / "no medium" | Aguarda `LTFS_MEDIUM_WAIT_TIMEOUT` |
| Processo/device travado | transport failure / I/O error | `kill_hung` → SCSI reset → restart |
| Erro SCSI hardware | `-29998` / sense `00001a` | Rewind + 1 retry → `hw_alert` |
| Índice corrompido | `extra blocks` / `-5000` | ltfsck → deep-recovery → `hw_alert` |
| Power-on-reset recorrente | `LTFS30270I` × 2 | `hw_alert` imediato |

### 4.2 `ltfs_recovery.py` — Auto-heal e cursor de escrita

**Localização NAS**: `/usr/local/tools/ltfs_recovery.py`
**Localização dev**: `tools/ltfs_recovery.py`

**Modos de operação:**

```bash
# Operações de mount/unmount
python3 ltfs_recovery.py --orchestrated-mount   # mount com lock exclusivo
python3 ltfs_recovery.py --orchestrated-stop    # unmount orquestrado

# Diagnóstico e recovery
python3 ltfs_recovery.py --diagnose             # JSON com diagnóstico
python3 ltfs_recovery.py --self-heal [--debug]  # auto-heal completo
python3 ltfs_recovery.py --self-heal-deep       # com ltfsck --deep-recovery

# Cursor de escrita (checkpoint por arquivo — analogia download manager)
python3 ltfs_recovery.py --cursor-open   --volser NC2508
python3 ltfs_recovery.py --cursor-update --volser NC2508 --file path/relativo
python3 ltfs_recovery.py --cursor-close  --volser NC2508
python3 ltfs_recovery.py --cursor-status --volser NC2508
python3 ltfs_recovery.py --cursor-recover --volser NC2508
python3 ltfs_recovery.py --cursor-list
```

**Sistema de cursor (checkpoint de escrita):**
- Analogia ao gerenciador de downloads: retoma do último arquivo confirmado após crash
- Cada arquivo escrito na fita gera checkpoint atômico (write `.tmp` → `rename`)
- Em caso de crash: `cursor-recover` lista confirmados e arquivos para re-fila
- Armazenado em: `/var/lib/ltfs/cursors/<VOLSER>.json`

**Lock files:**

| Lock | Caminho | Usado por |
|------|---------|-----------|
| sg0 orchestrator | `/run/lock/ltfs-orchestrator.lock` | ltfs_recovery.py sg0 |
| sg1 orchestrator | `/run/lock/ltfs-orchestrator-sg1.lock` | ltfs-fc-stable-start sg1 |
| Operação exclusiva sg0 | `/run/lock/ltfs-tape-exclusive.lock` | _run_exclusive_operation sg0 |

> ⚠️ **ATENÇÃO — deadlock corrigido em 2026-05-18 (L1):**
> `orchestrated_mount()` NÃO usa `_run_exclusive_operation`.
> `ltfs-fc-stable-start` gerencia seu próprio flock em `LTFS_ORCH_LOCK`.
> Usar `_run_exclusive_operation` causa deadlock permanente (timeout 8 min).
> A função chama `_stop_conflicting_services()` e `_run_orchestration_command()` diretamente.

### 4.3 `tape_dual_recovery.py` — Monitor dual de recovery

**Localização dev**: `tools/tape_dual_recovery.py`
**Executado de**: homelab (192.168.15.2), SSHeia para NAS (192.168.15.4)

```bash
python3 tools/tape_dual_recovery.py                    # stop + self-heal sg0 e sg1
python3 tools/tape_dual_recovery.py --skip-stop        # só self-heal (fitas já recolhidas)
python3 tools/tape_dual_recovery.py --mount            # orchestrated-mount em vez de self-heal
python3 tools/tape_dual_recovery.py --host 192.168.15.4
```

Exibe duas barras de progresso simultâneas (rich) com marcadores de fase mapeados
para percentual de conclusão.

### 4.4 `ltfs-cache-flush.service`

Substituído por `tape-manager flush`:
`ExecStart=/usr/local/bin/tape-manager flush`

---

## 5. Procedimentos Operacionais

### 5.1 Mount manual (bypass do serviço)

Usar quando o serviço falha em `activating` por lock, timeout ou deadlock:

```bash
# sg0
ssh homelab "ssh nas '/usr/local/ltfs-patched/bin/ltfs /mnt/tape/lto6 \
  -o devname=/dev/sg0 -o work_directory=/var/lib/ltfs/work -o nonempty'"

# sg1 (device atual: sg2)
ssh homelab "ssh nas '/usr/local/ltfs-patched/bin/ltfs /mnt/tape/lto6-sg1 \
  -o devname=/dev/sg2 -o work_directory=/var/lib/ltfs/work-sg1 -o nonempty'"
```

### 5.2 Reset SCSI antes de montar

Sempre executar antes de qualquer tentativa de mount após falha:

```bash
ssh homelab "ssh nas 'sg_reset --device /dev/sg0 && sleep 5 && sg_inq /dev/sg0'"
ssh homelab "ssh nas 'sg_reset --device /dev/sg2 && sleep 5 && sg_inq /dev/sg2'"
```

### 5.3 Limpar locks obsoletos

```bash
ssh homelab "ssh nas '
  for f in /run/lock/ltfs*.lock; do
    [ -f \"\$f\" ] || continue
    pid=\$(grep -oP \"pid=\\K[0-9]+\" \"\$f\" 2>/dev/null \
      || python3 -c \"import json,sys; print(json.load(open(chr(39)+\\\"\$f\\\"+chr(39)))[chr(39)pid\$chr(39)])\" 2>/dev/null)
    if [ -n \"\$pid\" ] && ! kill -0 \"\$pid\" 2>/dev/null; then
      echo \"Removendo lock obsoleto: \$f (PID \$pid morto)\"
      rm -f \"\$f\"
    fi
  done
'"
```

### 5.4 Verificar estado completo dos drives

```bash
ssh homelab "ssh nas '
  echo === Serviços ===
  systemctl is-active ltfs-lto6.service ltfs-lto6-sg1.service
  echo === Mountpoints ===
  mountpoint /mnt/tape/lto6 /mnt/tape/lto6-sg1
  df -h /mnt/tape/lto6 /mnt/tape/lto6-sg1 2>/dev/null
  echo === Devices ===
  lsscsi -g | grep tape
  echo === Locks ===
  ls -la /run/lock/ltfs*.lock 2>/dev/null
'"
```

### 5.5 Reenumerar devices após troca de hardware (receptor óptico, cabo SAS)

```bash
# 1. Rescan do barramento SCSI
ssh homelab "ssh nas 'echo \"- - -\" | sudo tee /sys/class/scsi_host/host*/scan'"
sleep 5

# 2. Confirmar novo mapeamento
ssh homelab "ssh nas 'lsscsi -g | grep tape'"

# 3. Atualizar env file se device mudou (ex: sg1→sg2, nst1→nst2)
ssh homelab "ssh nas 'sudo sed -i \
  \"s|/dev/sg1|/dev/sg2|g; s|/dev/nst1|/dev/nst2|g; s|/dev/st1|/dev/st2|g\" \
  /etc/default/ltfs-lto6-sg1'"

# 4. Reload e restart
ssh homelab "ssh nas 'systemctl daemon-reload && systemctl restart ltfs-lto6-sg1.service'"
```

### 5.6 Diagnóstico de power-on-reset recorrente

```
Sintoma no journal/ltfsck:
  LTFS30270I A power-on-reset happened on drive HUJ548570K
  LTFS30263I LOCATE returns Disrupted transport failure (-21720)
  LTFS12037E Cannot seek: backend call failed (-21723)
  LTFS16080E Cannot check volume (8)

Causa: hardware — NÃO é resolvível por software.

Checklist físico (em ordem):
  1. Cabo de alimentação do drive (desconectar e reconectar firmemente)
  2. Cabo SAS/FC (reconectar nos dois extremos)
  3. Receptor óptico/SFP (trocar se intermitente — foi a causa em 2026-05-18)
  4. Fonte de alimentação (verificar tensões)
  5. Substituir drive se todos acima estiverem OK
```

### 5.7 Formatação de fita nova (mkltfs)

> ⚠️ **DESTRUTIVO — apaga todos os dados permanentemente. Exige confirmação explícita.**

```bash
# 1. Ler serial MAM (pode ser maior que 6 chars)
ssh homelab "ssh nas 'sg_read_attr --partition=0 /dev/sg2 2>&1 | grep -iE \"barcode|serial\"'"

# 2. Formatar — serial DEVE ter EXATAMENTE 6 caracteres alfanuméricos ASCII
ssh homelab "ssh nas 'mkltfs --device /dev/sg2 --tape-serial XXXXXX --volume-name NOME'"

# Regra de serial:
#   - Preferir barcode físico colado na fita (ex: NC2508, EVATWG)
#   - Se MAM retornar serial longo (ex: EVATWG1M8E), usar primeiros 6: EVATWG
#   - Nunca usar mais de 6 chars (mkltfs retorna erro LTFS15029E)
```

### 5.8 Recovery completo após falha de escrita (cursor)

```bash
# Ver estado do cursor
ssh homelab "ssh nas 'python3 /usr/local/tools/ltfs_recovery.py --cursor-status --volser NC2508'"

# Recuperar após crash (lista confirmados e para re-fila)
ssh homelab "ssh nas 'python3 /usr/local/tools/ltfs_recovery.py --cursor-recover --volser NC2508'"

# Ou via tape-manager (faz ltfsck + cursor-recover + remount)
ssh homelab "ssh nas 'tape-manager recover'"
ssh homelab "ssh nas 'tape-manager recover --deep'"  # se ltfsck normal falhar
```

---

## 6. Lições Aprendidas

### L1 — Deadlock flock: orchestrated_mount + ltfs-fc-stable-start
**Data**: 2026-05-18
**Sintoma**: Serviço fica em `activating` por exatamente 8 minutos e morre por timeout.
Apenas uma linha de log: `Iniciando operação exclusiva LTFS: mount`.
**Causa**: `orchestrated_mount()` usava `_run_exclusive_operation` que segurava flock
em `LTFS_ORCH_LOCK` enquanto `ltfs-fc-stable-start` tentava adquirir flock no mesmo
arquivo via novo file descriptor → deadlock permanente.
**Correção aplicada**: `orchestrated_mount()` chama `_stop_conflicting_services()` e
`_run_orchestration_command()` diretamente, sem `_run_exclusive_operation`.
**Regra**: Se um script externo gerencia seu próprio flock no mesmo arquivo de lock,
NÃO envolver com `_run_exclusive_operation`. Verificar dupla aquisição antes de usar.

---

### L2 — Troca de receptor óptico reenumera device SCSI
**Data**: 2026-05-18
**Sintoma**: Após troca do receptor FC, `/dev/sg1` → "Device not ready"; surge `/dev/sg2`.
`lsscsi -g` mostra novo endereço SCSI `[7:0:1:0]` onde antes era `[7:0:0:0]`.
**Causa**: Kernel cria nova entrada SCSI para o novo path óptico (LUN diferente).
**Correção aplicada**: Atualizado `/etc/default/ltfs-lto6-sg1` com sg2/nst2/st2.
**Regra**: Após qualquer troca de hardware no path SAS/FC, executar `lsscsi -g` antes
de tentar montar. Atualizar env file se o device mudou.

---

### L3 — Executar sg_reset antes de cada tentativa de mount
**Data**: 2026-05-18
**Sintoma**: `Disrupted transport failure`, `connection down`, `power-on-reset` impedem mount
e ltfsck mesmo com o drive fisicamente funcional.
**Causa**: Estado SCSI sujo acumulado de falhas anteriores não é limpo automaticamente.
**Correção aplicada**: `_flush_scsi_port()` em `tape_manager.py` executa
`sg_reset --device` + 5s de espera + `sg_inq` de confirmação antes de qualquer mount.
Também chamado em `kill_hung` e `rewind_retry`.
**Regra**: `sg_reset` antes de mount é preventivo e não apaga dados. Sempre incluir
no fluxo de recovery.

---

### L4 — Lock files com PID morto bloqueiam silenciosamente
**Data**: 2026-05-18
**Sintoma**: Operações de mount/recovery ficam presas sem mensagem de erro clara.
**Causa**: `fcntl.flock` é liberado com a morte do processo mas o arquivo `.lock` permanece.
Código que verifica o PID do arquivo (não o flock em si) fica aguardando processo morto.
**Correção aplicada**: `_clear_stale_lock()` em `tape_manager.py` usa `os.kill(pid, 0)`
para verificar se o processo existe antes de remover o lock.
**Regra**: Sempre verificar e limpar locks obsoletos antes de mount/recovery.
`_start_precheck()` faz isso automaticamente no `tape_manager.py`.

---

### L5 — mkltfs exige serial de exatamente 6 caracteres
**Data**: 2026-05-18
**Sintoma**: `LTFS15029E Tape serial must be 6 characters.`
**Causa**: MAM serial (`sg_read_attr`) retorna o serial completo do fabricante (10+ chars,
ex: `EVATWG1M8E`). mkltfs rejeita qualquer coisa diferente de 6 chars.
**Correção**: Usar barcode físico da fita (normalmente 6 chars) ou primeiros 6 do MAM.
**Regra**: Confirmar barcode físico com o usuário antes de rodar mkltfs. Nunca usar
o MAM serial completo diretamente.

---

### L6 — Power-on-reset recorrente é falha de hardware, não software
**Data**: 2026-05-18
**Sintoma**: `LTFS30270I A power-on-reset happened` aparece em ltfsck e mkltfs.
`READPOS` e `LOCATE` dão `Command TIMEOUT`. Nenhuma operação de software resolve.
**Causa raiz**: Instabilidade no receptor óptico FC (substituído e resolvido em 2026-05-18).
Pode ser também: cabo de alimentação, cabo SAS, ou drive com defeito.
**Correção aplicada**: `_detect_hardware_error()` detecta o padrão; `tape_manager.py`
escala para `hw_alert` imediatamente com checklist físico via Telegram.
**Regra**: Ao detectar power-on-reset recorrente, não tentar mais operações de software.
Inspecionar hardware na ordem: receptor óptico → cabo alimentação → cabo SAS → drive.

---

### L7 — Índice LTFS corrompido (extra blocks) é recuperável com ltfsck
**Data**: 2026-05-18
**Sintoma**: `LTFS11220E Medium check failed: extra blocks detected. Run ltfsck.`
Mount falha com XML parse error `-5000`.
**Causa**: Sessão de escrita encerrada abruptamente sem sync/unmount limpo (crash, SIGKILL).
**Correção**: `ltfsck /dev/sgX` corrige o índice sem perda de dados (apenas reescreve
o ponteiro de índice). Se ltfsck normal falhar, tentar `ltfsck --deep-recovery`.
**Regra**: Sempre tentar ltfsck antes de cogitar mkltfs — dados são preservados enquanto
o drive conseguir ler os blocos.

---

## 7. Mapa de Arquivos no NAS

```
/usr/local/tools/
├── tape_manager.py          # gerenciador de ciclo de vida
├── ltfs_recovery.py         # auto-heal, cursor, orchestration
└── tape_dual_recovery.py    # monitor dual (roda no homelab)

/usr/local/bin/
└── tape-manager             # symlink → /usr/local/tools/tape_manager.py

/usr/local/sbin/
├── ltfs-fc-stable-start     # script de mount LTFS com flock próprio
└── ltfs-lto6-stop           # script de unmount

/etc/default/
├── ltfs-lto6                # env sg0 (device: /dev/sg0, nst0)
└── ltfs-lto6-sg1            # env sg1 (device: /dev/sg2, nst2 — pós receptor óptico)

/etc/systemd/system/
├── ltfs-lto6.service        # serviço sg0
└── ltfs-lto6-sg1.service    # serviço sg1

/var/lib/ltfs/
├── cursors/<VOLSER>.json    # checkpoints de escrita por volser
├── current_volser.txt       # volser atual sg0
├── work/                    # workdir ltfs sg0
├── work-sg1/                # workdir ltfs sg1
├── self_heal_state.json     # estado do self-heal sg0
└── self_heal_state_sg1.json # estado do self-heal sg1

/run/lock/
├── ltfs-orchestrator.lock       # operações sg0 (ltfs_recovery.py)
├── ltfs-orchestrator-sg1.lock   # operações sg1 (ltfs-fc-stable-start)
└── ltfs-tape-exclusive.lock     # operações exclusivas sg0

/var/log/lto6/tape_manager.log   # log do tape_manager
/var/spool/lto6-cache/           # staging area (LTFS_CACHE_DIR)
/mnt/tape/lto6/                  # mountpoint sg0
/mnt/tape/lto6-sg1/              # mountpoint sg1
/run/ltfs-export/lto6/           # bind mount exportado sg0
/run/ltfs-export/lto6-sg1/       # bind mount exportado sg1
```

---

## 8. Notificações Telegram

Credenciais em `/home/homelab/myClaude/.env` no NAS/homelab:
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

O `tape_manager.py` notifica via Telegram em:
- Início de cada operação (start, flush, stop, recover)
- Cada tentativa de mount com resultado
- Detecção de problemas (lock stale, fita ausente, processo travado)
- Escalada para hw_alert (erro SCSI, power-on-reset)
- Conclusão com status final

Configurável via variáveis de ambiente:
```bash
TG_ENV_FILE=/outro/arquivo.env tape-manager start   # outro arquivo de credenciais
--no-notify                                          # desabilita todas as notificações
```

---

## 9. Adendo Operacional — SG1 Rotate no Homelab (2026-05-19)

Em 2026-05-19 foi confirmado que o pipeline lógico da fita `sg1` no homelab depende do share CIFS `//192.168.15.4/LTO6_SG1` montado em `/mnt/tape_sg1`, e nao de um `rsync` direto do homelab para `/mnt/tape/lto6-sg1`.

Resumo do saneamento aplicado:

- `create_snapshot.logrotate` recebeu `su root root`, permitindo que o rotate volte a enfileirar arquivos.
- `tape-log-spool-drain` passou a exigir mount real via `REQUIRE_MOUNTPOINT=/mnt/tape_sg1`.
- `homelab-tape-log-drain-sg1.service` passou a declarar `RequiresMountsFor=/mnt/tape_sg1/logs`.
- o mount do share `LTO6_SG1` foi formalizado em `mnt-tape_sg1.mount` + `mnt-tape_sg1.automount`.
- backlog local oculto, escrito enquanto o CIFS estava down, foi recuperado e reenviado para a fita.

Fluxo correto:

```text
logrotate -> /var/spool/tape-log-buffer/incoming
          -> routes/tape_sg1
          -> /mnt/tape_sg1/logs
          -> //192.168.15.4/LTO6_SG1
          -> /run/ltfs-export/lto6-sg1
          -> /mnt/tape/lto6-sg1/logs
```

Referencias detalhadas:

- `docs/INCIDENTS/LTO_SG1_ROTATE_PATH_RECOVERY_2026-05-19.md`
- `docs/LESSONS_LEARNED_LTO_SG1_ROTATE_2026-05-19.md`
