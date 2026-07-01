# Incidente — SG0 com concorrência implícita, timers mortos e backlog longo — 2026-05-21

> Diagnóstico e correção do fluxo principal de fita `sg0`, cobrindo concorrência,
> rearmamento de timers e separação real entre os dois drives físicos.

---

## Resumo Executivo

Em 2026-05-21 o `sg0` estava escrevendo de fato, mas o desenho operacional tinha
três fragilidades:

1. `nextcloud-tape-backup.service` e `nvme-tape-drain.service` podiam ser
   disparados enquanto um `ltfs-cache-flush.service` anterior ainda estava em
   andamento.
2. `nextcloud-tape-backup.timer` e `nvme-tape-drain.timer` estavam morrendo por
   `Dependency failed`, deixando o agendamento principal degradado.
3. O gate `tape-access` ainda sugeria uma fila global única, o que não refletia
   a realidade de dois drives físicos independentes (`sg0` e `sg1`).

O saneamento foi concluído com:

- guard de sessão anterior com saída limpa e observação no journal
- timers do `sg0` rearmados e desacoplados do mount no nível do timer
- escopo próprio de lock/fila para o `sg0`
- validação ao vivo no NAS de que os starts concorrentes passaram a encerrar sem
  disputa real da fita

---

## Estado Encontrado

Topologia viva validada em 2026-05-21:

- `sg0` / `st0` / `nst0` -> `/mnt/tape/lto6`
- `sg1` / `st1` / `nst1` -> `/mnt/tape/lto6-sg1`

Estado do `sg0` antes do ajuste:

- `ltfs-cache-flush.service`: `activating/start` por longo período
- `nextcloud-tape-backup.timer`: `inactive/dead` por dependência
- `nvme-tape-drain.timer`: `inactive/dead` por dependência
- backlog real em `/var/spool/lto6-cache`
- evidências repetidas de `flush: ok`, logo não era deadlock de escrita

O ponto mais sutil era que `activating` não significava falha. O `flush`
seguia processando um snapshot grande e muito fragmentado, especialmente dentro
de `.gradle`, com centenas de milhares de arquivos pequenos.

---

## Causas Raiz

### Causa 1 — serviços concorrentes não tratavam `activating` como sessão ativa

O `ltfs-cache-flush.service` pode ficar horas em `activating` durante a cópia do
staging para a LTFS. Sem um guard explícito, outros serviços podiam tentar
iniciar no meio desse processo.

### Causa 2 — dependência no timer em vez do service

Os timers `nextcloud-tape-backup.timer` e `nvme-tape-drain.timer` carregavam
dependências de LTFS no próprio timer. Isso fazia o agendamento morrer antes da
janela de execução, quando a verificação correta deveria ocorrer apenas no
service.

### Causa 3 — gate global induzia premissa errada entre `sg0` e `sg1`

O `tape-access` usava caminhos fixos globais para lock e fila. Mesmo com dois
drives físicos independentes, a topologia de software ainda sugeria um funil
único para todos os jobs de fita.

---

## Correções Aplicadas

### Repositório

- `tools/tape_session_guard.sh`
  - novo helper para sair com observação e `exit 0` quando existe sessão
    anterior ativa ou lock ocupado
- `tools/tape-access`
  - passou a aceitar `TAPE_ACCESS_LOCKFILE`, `TAPE_ACCESS_QUEUE_DIR` e
    `TAPE_ACCESS_HOLDER_FILE`
- `systemd/nextcloud-tape-backup.service.d/30-no-overlap.conf`
  - backup encapsulado por `tape-session-guard`
- `systemd/nvme-tape-drain.service.d/30-no-overlap.conf`
  - drain encapsulado por `tape-session-guard`
- `systemd/lto6-drain-backups.service.d/50-tape-gate.conf`
  - drain legado alinhado ao mesmo comportamento
- `systemd/nextcloud-tape-backup.timer.d/20-no-ltfs-require.conf`
  - remove `After=` e `Requires=` do timer
- `systemd/nvme-tape-drain.timer.d/20-no-ltfs-require.conf`
  - remove `After=` e `Requires=` do timer
- `systemd/ltfs-cache-flush.service.d/70-rearm-timer-on-exit.conf`
  - **obsoleto em 2026-05-25**: removido porque rearmar o timer via
    `ExecStopPost` impedia janelas seguras de recuperação. O retorno de timers
    passou a ser responsabilidade de `ltfs_recovery.py` após validação saudável.
- `systemd/ltfs-lto6.service.d/65-sg0-tape-access-scope.conf`
  - escopa fila/lock para `sg0`
- `systemd/nextcloud-tape-backup.service.d/35-sg0-tape-access-scope.conf`
  - escopo de `sg0` herdado no backup
- `systemd/nvme-tape-drain.service.d/35-sg0-tape-access-scope.conf`
  - escopo de `sg0` herdado no drain

### Produção no NAS

- helper publicado em `/usr/local/sbin/tape-session-guard`
- drop-ins copiados para `/etc/systemd/system/...`
- `systemctl daemon-reload` executado
- timers reativados sem interromper o `flush` em andamento

---

## Nova Topologia de Concorrência

### sg0

```text
nextcloud-tape-backup.service
nvme-tape-drain.service
lto6-drain-backups.service
            │
            └─ tape-session-guard
                  │
                  ├─ observa ltfs-cache-flush.service em active/activating/...
                  ├─ observa lock ocupado
                  └─ só executa se o sg0 estiver livre

ltfs-lto6.service
nextcloud-tape-backup.service
nvme-tape-drain.service
            │
            └─ TAPE_ACCESS_LOCKFILE=/run/lock/tape-access-sg0.lock
               TAPE_ACCESS_QUEUE_DIR=/run/tape-queue-sg0
               TAPE_ACCESS_HOLDER_FILE=/run/tape-queue-sg0/current
```

### sg1

O `sg1` permaneceu independente:

- drive físico distinto
- mountpoint distinto
- pipeline de logs distinto
- sem passar pelo gate scoped de `sg0`

---

## Validação Ao Vivo

### Starts concorrentes encerrando sem disputa

Validações manuais no NAS:

- `2026-05-21 01:44:57 -03`
  - `nextcloud-tape-backup.service` encerrou com observação de sessão anterior
    ativa em `ltfs-cache-flush.service (state=activating)`
- `2026-05-21 01:45:37 -03`
  - `nvme-tape-drain.service` encerrou com a mesma observação
- `2026-05-21 02:00:01 -03`
  - nova tentativa de `nextcloud-tape-backup.service` voltou a sair sem
    concorrência

Exemplo de mensagem registrada:

```text
[OBS] sessão anterior ainda ativa em ltfs-cache-flush.service (state=activating)
```

### Timers do sg0 rearmados

Estado observado após o saneamento:

- `nextcloud-tape-backup.timer`: `active/waiting`
- `nvme-tape-drain.timer`: `active/waiting`
- `ltfs-cache-flush.timer`: `active/running` enquanto o flush longo seguia em execução

### Gate scoped de sg0

Variáveis validadas nos services:

```bash
TAPE_ACCESS_LOCKFILE=/run/lock/tape-access-sg0.lock
TAPE_ACCESS_QUEUE_DIR=/run/tape-queue-sg0
TAPE_ACCESS_HOLDER_FILE=/run/tape-queue-sg0/current
```

Consulta validada:

```bash
TAPE_ACCESS_LOCKFILE=/run/lock/tape-access-sg0.lock \
TAPE_ACCESS_QUEUE_DIR=/run/tape-queue-sg0 \
TAPE_ACCESS_HOLDER_FILE=/run/tape-queue-sg0/current \
/usr/local/sbin/tape-access status
```

Resultado esperado quando livre:

```text
=== TAPE ACCESS STATUS ===
LIVRE
```

---

## Estado Operacional no Fechamento

Em `2026-05-21 10:39 -03`:

- `sg0` seguia montado e gravando
- `ltfs-cache-flush.service` seguia em `activating`, mas com `flush: ok`
- backlog em `/var/spool/lto6-cache`: `50G`
- pendências: `347974` arquivos
- fila lógica do `sg0`: livre
- `sg1` seguia saudável, com spool de logs vazio

Interpretação correta:

- existe backlog real no `sg0`
- não existe deadlock de lock/fila
- o gargalo corrente é volume fragmentado de arquivos pequenos, não disputa
  entre services

---

## Impacto

- os dois drives ficaram coerentes com a topologia física real
- o `sg0` não aceita mais sobreposição perigosa de jobs
- a observabilidade ficou melhor: agora o journal diferencia "ocupado" de
  "falhou"
- o agendamento do `sg0` voltou a ficar armado sem depender de reativação manual

---

## Errata 2026-05-25 — rearm de timer movido para o orquestrador

O drop-in `systemd/ltfs-cache-flush.service.d/70-rearm-timer-on-exit.conf` foi
removido após novo incidente de recovery no `sg0`. Durante recuperação, o timer
precisa permanecer parado e, em alguns casos, mascarado em runtime. Rearmá-lo a
partir do `ExecStopPost` do próprio serviço de flush gerava `stop-post` preso e
reiniciava escrita antes da validação do catálogo.

Estado correto desde 2026-05-25:

- `ltfs_recovery.py` suspende services/timers interferentes.
- Timers são mascarados em runtime durante recovery, quando configurado.
- O estado anterior é salvo em `LTFS_SUSPEND_STATE_FILE`.
- Apenas units que estavam ativas antes são religadas após `--check` saudável.
- O incidente detalhado está em
  `docs/INCIDENTS/LTO_SG0_POINTER_RECOVERY_2026-05-25.md`.

---

## Arquivos Relevantes

- `tools/tape_session_guard.sh`
- `tools/tape-access`
- `systemd/nextcloud-tape-backup.service.d/30-no-overlap.conf`
- `systemd/nvme-tape-drain.service.d/30-no-overlap.conf`
- `systemd/lto6-drain-backups.service.d/50-tape-gate.conf`
- `systemd/nextcloud-tape-backup.timer.d/20-no-ltfs-require.conf`
- `systemd/nvme-tape-drain.timer.d/20-no-ltfs-require.conf`
- `tools/ltfs_recovery.py`
- `systemd/ltfs-lto6.service.d/65-sg0-tape-access-scope.conf`
- `systemd/nextcloud-tape-backup.service.d/35-sg0-tape-access-scope.conf`
- `systemd/nvme-tape-drain.service.d/35-sg0-tape-access-scope.conf`
- `docs/tape-archive-paths.md`
