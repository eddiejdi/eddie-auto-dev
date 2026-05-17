# ltfs-lto6.service: Loop Start→Stop Imediato — 2026-05-15

## Resumo

Após `ltfsck --full-recovery` da fita NC2508, o serviço `ltfs-lto6.service` entrou em loop de start→stop com duração de ~103ms. A fita montava com sucesso (Gen=68, 98084 arquivos) mas o ExecStop era chamado imediatamente após o ExecStartPost concluir. Três bugs encadeados foram identificados e corrigidos.

---

## Causa Raiz — 3 Bugs Encadeados

### Bug 1: `OnBootSec` já expirado dispara imediatamente ao restart do timer

O ExecStartPost executa `systemctl restart ltfs-idle-unmount.timer`. O timer tinha:

```ini
[Timer]
OnBootSec=10min
OnUnitActiveSec=5min
```

`OnBootSec=10min` é relativo ao boot do sistema. Como o boot havia ocorrido horas antes, ao reiniciar o timer o prazo já estava expirado → disparava **imediatamente** ao ser ativado.

### Bug 2: `OnUnitActiveSec` dispara imediatamente quando overdue

Mesmo corrigindo `OnBootSec`, o `OnUnitActiveSec=5min` dispara imediatamente se o serviço `ltfs-idle-unmount.service` rodou há mais de 5 minutos. Documentado em `man systemd.timer`:

> *"if the relative time is longer than the activation/deactivation cycle, the timer fires immediately (at the next opportunity)"*

Como o serviço havia rodado horas antes, `OnUnitActiveSec=5min` sempre disparava imediatamente ao reativar o timer.

**Solução:** usar `OnUnitInactiveSec` em vez de `OnUnitActiveSec`. O `OnUnitInactiveSec` conta a partir da última *desativação* do serviço — se o serviço nunca rodou nesta sessão do timer, não há referência e ele não dispara imediatamente.

### Bug 3: `%s` expandido como especificador systemd

O ExecStartPost para resetar o timestamp de I/O foi escrito como:

```ini
ExecStartPost=/bin/bash -c "date +%s > /run/ltfs-last-io"
```

O systemd expande `%s` para o **shell do usuário** (ex: `/bin/bash`), resultando no comando real:

```
date +/bin/bash > /run/ltfs-last-io
```

O arquivo `/run/ltfs-last-io` ficava com conteúdo `/bin/bash` em vez de um timestamp Unix. O script `ltfs-idle-unmount.sh` fazia aritmética `$(( NOW - LAST_IO ))` onde `LAST_IO=/bin/bash`, falhava silenciosamente e caía no branch de unmount.

**Especificadores systemd relevantes:** `%s` = shell do usuário, `%n` = nome da unit, `%u` = usuário, `%h` = home. Para usar `%` literal: escrever `%%`.

---

## Fixes Aplicados

### Fix 1 — `ltfs-idle-unmount.timer`

Arquivo: `/etc/systemd/system/ltfs-idle-unmount.timer` na NAS (192.168.15.4)

```ini
[Unit]
Description=Verificacao periodica de inatividade da fita

[Timer]
OnActiveSec=5min           # primeira execução 5min após ativação do timer
OnUnitInactiveSec=5min     # reexecutar 5min após cada execução terminar

[Install]
WantedBy=timers.target
```

**Antes:** `OnBootSec=10min` + `OnUnitActiveSec=5min`
**Depois:** `OnActiveSec=5min` + `OnUnitInactiveSec=5min`

### Fix 2 — `60-restart-timers.conf`

Arquivo: `/etc/systemd/system/ltfs-lto6.service.d/60-restart-timers.conf`

```ini
[Service]
ExecStartPost=/bin/systemctl restart ltfs-cache-flush.timer
ExecStartPost=/bin/systemctl restart lto6-selfheal.timer
ExecStartPost=/bin/systemctl restart ltfs-idle-unmount.timer
# %%s escapa o especificador systemd (sem %% vira /bin/bash)
ExecStartPost=/bin/bash -c "date +%%s > /run/ltfs-last-io"
```

Reset de `/run/ltfs-last-io` com `%%s` corretamente escapado garante que o idle-unmount conta inatividade a partir do momento do mount, não de I/O anterior.

---

## Método de Diagnóstico

O loop foi identificado pelo journal geral ao redor do evento de stop:

```bash
journalctl --since "HH:MM:SS" --until "HH:MM:SS" --no-pager \
  | grep -iE "ltfs-lto6|Stopping|idle.unmount"
```

Revelou:
```
12:17:49 Started ltfs-idle-unmount.timer
12:17:49 Finished ltfs-lto6.service
12:17:49 Starting ltfs-idle-unmount.service   ← disparo imediato!
12:17:49 ltfs-idle-unmount.sh: line 28: /bin/bash: syntax error  ← %s expandido
12:17:50 Fita inativa por s — iniciando desmonte seguro
12:17:50 Stopping ltfs-lto6.service
```

Para verificar o comando real que o systemd executa (após expansão de especificadores):
```bash
systemctl status ltfs-lto6.service | grep ExecStartPost
# Process: ... ExecStartPost=/bin/bash -c date +/bin/bash > /run/ltfs-last-io
# Acima revela o bug: %s virou /bin/bash
```

---

## Resultado

- `ltfs-lto6.service` estável em `active (exited)` desde 12:23:29
- `ltfs-idle-unmount.timer` disparando corretamente cada 5min (não imediatamente)
- Drain de 158GB retomado: `lto6-drain-backups.service` ativo desde 12:24:40
- Sync periódico da fita confirmado: Gen 68 → 74 em ~30min de operação

---

## Lições Aprendidas

1. **`OnBootSec` + `systemctl restart`** = disparo imediato se boot foi há mais de N segundos. Nunca usar `OnBootSec` em timers que precisam ser reiniciados manualmente.

2. **`OnUnitActiveSec`** = disparo imediato se o serviço ativado rodou há mais de N segundos. Para timers periódicos que sobrevivem a restarts, preferir **`OnUnitInactiveSec`**.

3. **Especificadores systemd em ExecStart/Post/Stop:** `%s`, `%n`, `%u`, `%h`, etc. são expandidos. Usar `%%` para `%` literal. Sempre validar com `systemctl status` e inspecionar a linha `Process:` para ver o comando real expandido.

4. **Diagnóstico de stop imediato:** usar `journalctl` com janela estreita (±10s ao redor do evento) filtrando pelo nome do serviço + "Stopping" para identificar o ator externo.

---

## Arquivos Alterados (NAS 192.168.15.4)

| Arquivo | Mudança |
|---|---|
| `/etc/systemd/system/ltfs-idle-unmount.timer` | `OnBootSec+OnUnitActiveSec` → `OnActiveSec+OnUnitInactiveSec` |
| `/etc/systemd/system/ltfs-lto6.service.d/60-restart-timers.conf` | Adicionado reset de `ltfs-last-io` com `%%s` correto |

Tags: `ltfs`, `nas`, `systemd`, `timer`, `bug`, `infraestrutura`, `lto6`, `incidente`
