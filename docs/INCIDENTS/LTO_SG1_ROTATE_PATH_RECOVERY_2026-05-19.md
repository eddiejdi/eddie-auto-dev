# Incidente — SG1 Rotate do Homelab Gravando Fora da Fita — 2026-05-19

> Diagnóstico e correção do pipeline de rotação de logs do homelab para a fita lógica `sg1`.

---

## Resumo Executivo

Em 2026-05-19 foi confirmado que a fita lógica `sg1` continuava existindo e estava montada no NAS, mas o pipeline de rotação do homelab não estava chegando de forma confiável até a LTFS.

Dois problemas independentes se combinavam:

1. `homelab-tape-logrotate.service` abortava em `create_snapshot.log` por falta de `su` no snippet do `logrotate`.
2. O mount `//192.168.15.4/LTO6_SG1 -> /mnt/tape_sg1` tinha falhado no homelab em 2026-05-18 22:28:12 -03. Com isso, o drain escrevia no diretório local subjacente, e não na fita exportada pelo NAS.

O saneamento foi concluído com correção de configuração, recuperação do backlog oculto e validação ponta a ponta.

---

## Topologia Correta

```text
/var/log/* + /home/homelab/* + /opt/homeassistant/*
        │
        └─ logrotate-tape.conf
              │
              └─ /var/spool/tape-log-buffer/incoming
                    │
                    └─ tape-logrotate-runner
                          │
                          └─ /var/spool/tape-log-buffer/routes/tape_sg1
                                │
                                └─ homelab-tape-log-drain-sg1.service
                                      │
                                      └─ /mnt/tape_sg1/logs
                                            │
                                            └─ CIFS //192.168.15.4/LTO6_SG1
                                                  │
                                                  └─ /run/ltfs-export/lto6-sg1
                                                        │
                                                        └─ /mnt/tape/lto6-sg1/logs
```

---

## Evidências do Problema

### 1. Rotate quebrado

O `journalctl` do `homelab-tape-logrotate.service` mostrava:

```text
error: skipping "/var/log/create_snapshot.log" because parent directory has insecure permissions
```

O snippet `/usr/local/etc/logrotate-tape.d/create_snapshot` não declarava `su`, apesar de `/var/log` estar com permissões que exigiam isso para a política do `logrotate`.

### 2. Mountpoint lógico existia, mas o CIFS estava down

O homelab possuía o `fstab`:

```fstab
//192.168.15.4/LTO6_SG1 /mnt/tape_sg1 cifs ...
```

Mas o estado ao vivo era:

```text
mnt-tape_sg1.mount: failed
mount error(113): could not connect to 192.168.15.4
```

Enquanto o mount estava ausente, o serviço `homelab-tape-log-drain-sg1.service` continuava usando:

```ini
Environment=ROUTE_TARGET_ROOT=/mnt/tape_sg1/logs
```

Sem uma verificação explícita de `mountpoint`, o `rsync` passava a gravar no diretório local do host.

### 3. Backlog oculto no diretório subjacente

Após desmontagem isolada do namespace de mount, foi encontrado backlog local:

- 22 arquivos
- 158 MB
- incluindo `codex-sg1-rotate-test-20260519-024003.log`

Esse conteúdo não estava visível enquanto o CIFS estava montado novamente por cima do mesmo caminho.

---

## Causa Raiz

### Causa 1 — Snippet `create_snapshot.logrotate` incompatível com as permissões reais

O `logrotate` recusava o arquivo por falta de `su root root`.

### Causa 2 — Dependência implícita de mount remoto sem guarda operacional

O drain assumia que `/mnt/tape_sg1/logs` era a fita, mas não validava se `/mnt/tape_sg1` era um mount real.

### Causa 3 — Mount CIFS de `sg1` dependia de uma tentativa única

O path existia no `fstab`, mas sem a camada de `automount`, tornando a recuperação menos resiliente após falhas transitórias de conectividade com a NAS.

---

## Correções Aplicadas

### Repositório

- `scripts/create_snapshot.logrotate`
  - adicionado `su root root`
  - ativado `nocompress`, `dateext`, `dateformat`, `olddir` e `createolddir`
- `tools/backup/tape_log_spool_drain.sh`
  - adicionado `REQUIRE_MOUNTPOINT`
  - aborta quando o mount exigido não está ativo
- `systemd/homelab-tape-log-drain-sg1.service`
  - adicionado `RequiresMountsFor=/mnt/tape_sg1/logs`
  - adicionado `Environment=REQUIRE_MOUNTPOINT=/mnt/tape_sg1`
- `systemd/mnt-tape_sg1.mount`
  - unit explícita do CIFS `//192.168.15.4/LTO6_SG1`
- `systemd/mnt-tape_sg1.automount`
  - automount sob demanda com `TimeoutIdleSec=10min`
- `tests/test_tape_archive_paths.py`
  - cobertura para guardas de mount, snippet corrigido e units de mount/automount

### Produção

- instalado o snippet corrigido em `/usr/local/etc/logrotate-tape.d/create_snapshot`
- instalado o `tape-log-spool-drain` endurecido
- instalado `mnt-tape_sg1.mount` e `mnt-tape_sg1.automount`
- comentada a linha antiga do `fstab` para `LTO6_SG1`, evitando drift com o unit systemd
- religado o fluxo via `systemctl daemon-reload` e `enable --now mnt-tape_sg1.automount`

### Recuperação de dados

- backlog oculto copiado do diretório local subjacente para `/var/tmp/tape_sg1_hidden_backlog`
- backlog sincronizado para `/mnt/tape_sg1/logs`
- presença final confirmada em `/mnt/tape/lto6-sg1/logs` no NAS
- resíduo local oculto removido após sincronização

---

## Validação

### Testes locais

```bash
pytest -q tests/test_tape_archive_paths.py
```

### Validação operacional no host

- `mnt-tape_sg1.automount`: `enabled`, `active`
- `mnt-tape_sg1.mount`: `active`
- `homelab-tape-logrotate.timer`: `active`
- `homelab-tape-log-drain-sg1.timer`: `active`
- fila `routes/tape_sg1`: `0` arquivos pendentes

### Validação ponta a ponta

Foi criado um arquivo de teste temporário:

```text
codex-rotate-e2e.log-20260519-024959
```

O teste confirmou:

1. `homelab-tape-logrotate.service` carimbou o arquivo para `tape_sg1`
2. `homelab-tape-log-drain-sg1.service` drenou o arquivo com `synced=19 failed=0`
3. o arquivo apareceu em `/mnt/tape_sg1/logs`
4. o arquivo apareceu em `/mnt/tape/lto6-sg1/logs` no NAS

Ao final da verificação, o volume `sg1` possuía 204 arquivos em `logs/`.

---

## Impacto

- o rotate automático do homelab para a fita `sg1` voltou a funcionar
- escritas locais falsas em `/mnt/tape_sg1/logs` ficaram bloqueadas
- backlog que estava fora da LTFS foi reincorporado ao acervo da fita
- o path lógico `sg1` ficou coerente entre homelab, NAS e documentação

---

## Arquivos Relevantes

- `scripts/create_snapshot.logrotate`
- `tools/backup/tape_log_spool_drain.sh`
- `tools/backup/tape_logrotate_runner.sh`
- `systemd/homelab-tape-logrotate.service`
- `systemd/homelab-tape-logrotate.timer`
- `systemd/homelab-tape-log-drain-sg1.service`
- `systemd/homelab-tape-log-drain-sg1.timer`
- `systemd/mnt-tape_sg1.mount`
- `systemd/mnt-tape_sg1.automount`
- `docs/tape-archive-paths.md`
- `tests/test_tape_archive_paths.py`
