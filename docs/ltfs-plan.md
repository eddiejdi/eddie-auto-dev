# LTFS Auto Recap & Planos futuros

Este documento centraliza o novo comportamento do pipeline de recuperação LTFS.

## 1. Fluxo acionado por alertas

- **Alertmanager → `tools/alerting/ltfs_alert_handler.py`**: o webhook (`tools/alerting/alertmanager_telegram_webhook.py`) passa o cabeçalho `X-Alert-Type` para o handler que decide qual modo do `ltfs_recovery.py` executar.
  - Em produção, o handler pode executar o recovery remotamente no NAS via `LTFS_RECOVERY_SSH_TARGET`, mantendo o Grafana/Alertmanager no `homelab` e o LTFS no host das fitas.
  - `ltfs-catalog` dispara `ltfs_recovery --check`, e em caso de falha executa `--catalog-restore` antes de revalidar.
  - `ltfs-drive` e `ltfs-read` chamam `ltfs_recovery --drive-check`.
  - O handler respeita throttle (5 minutos por tipo) e registra offsets em `/tmp/ltfs_alert_state.json`.

## 2. Scripts de ajuda

- `tools/ltfs_recovery.py` fornece os modos:
  1. `--check` — valida mountpoint, `ltfs-catalog list` e espaço do df.
  2. `--catalog-restore` — importa o último `pg_dump` salvo em `/mnt/raid1/ltfs-cat-backups`.
  3. `--drive-check` — repete `--check` e confere `dmesg`.
  4. `--backup-catalog` — gera dumps/exports diários com retenção de 14 dias.
  5. `--prepare-mirror` — esboça o procedimento para adicionar a próxima fita.

- `tools/ltfs_backup_catalog.sh` pode ser acionado via `systemd` com `systemd/ltfs-backup-catalog.service` + `systemd/ltfs-backup-catalog.timer`, mantendo dumps recentes sem deixar Python rodando continuamente.
- Opcionalmente, centralize variáveis como `TAPE_CATALOG_DB`, `LTFS_BACKUP_ROOT` e `LTFS_MOUNT_POINT` em `/etc/default/ltfs-recovery`.

## 3. Workflow de testes e alertas

- O workflow `.github/workflows/nas-health-check.yml` agora chama:
  1. `python3 tools/ltfs_recovery.py --check`
  2. Em caso de falha (`returncode != 0`), `python3 tools/ltfs_recovery.py --catalog-restore`
  3. Novo check para confirmar o resultado.
- Os logs do workflow informam o status final para auditoria.

## 4. Preparação para a próxima fita

- Crie o novo volume e monte no slot secundário.
- Execute `python3 tools/ltfs_recovery.py --prepare-mirror` para atualizar o runbook (sem sincronizar dados automaticamente).
- Depois que a fita estiver pronta, adicione manualmente a entrada no catálogo (`tape_catalog.tapes`) e repita os checks.

## 5. Incidente real validado em 2026-03-31

- O alerta do Grafana estava correto: o catálogo aparecia indisponível porque o serviço `ltfs-lto6.service` continuava fixado em `/dev/sg0`, cuja fita `SG0R26` falhava ao ler o ANSI label.
- A automação não conseguia se recuperar sozinha nesse estado porque o `--check` só via o mount principal quebrado, e o serviço principal insistia no device errado.
- A fita `SG1R26` em `/dev/sg1` foi recuperada com `ltfsck -z /dev/sg1`, voltou a ficar consistente e montou normalmente em modo de prova.
- Após a validação, o override operacional do serviço foi trocado para `/dev/sg1`, `/dev/st1` e `/dev/nst1`; o mount principal `/mnt/tape/lto6` voltou a responder e `python3 /usr/local/tools/ltfs_recovery.py --check` passou a retornar sucesso.
- A fita `SG0R26` permaneceu com falha dura de leitura no início da mídia: `ltfsck -l`, `ltfsck --salvage-rollback-points` e `ltfsck -z` falharam do mesmo jeito, sempre em `Cannot read ANSI label: expected 80 bytes, but received 0`.
- O MAM de `SG0R26` ainda mostra rótulo LTFS (`RECOVER_SG0_20260326`), mas a área inicial necessária para mount não está legível; na prática, ela deve ficar em quarentena até teste físico em outro drive ou troca da mídia.
- O timer legado `lto6-selfheal.timer` foi desabilitado no NAS para evitar nova sondagem contínua; a recuperação passa a depender do fluxo orientado por alertas do Grafana/webhook.
- Após a reorganização física do NAS (cabos/FC/limpeza), a topologia mudou: a fita saudável `SG1R26` passou a responder em `/dev/sg0` e o slot `/dev/sg1` ficou livre para novos testes.
- O override operacional do serviço foi então ajustado novamente para `/dev/sg0`, `/dev/st0` e `/dev/nst0`; o mount principal voltou com sucesso em `/mnt/tape/lto6`.
- O teste cruzado final confirmou o diagnóstico: depois da troca física, a fita problemática `SG0R26` foi lida em `/dev/sg1` (drive serial `HUJ5485704`) e falhou do mesmo jeito em `ltfsck -l`, `ltfsck --salvage-rollback-points` e `ltfsck -z`, sempre no ANSI label.
- Com isso, o problema deixa de apontar para cabeamento ou para um único drive específico; a evidência operacional mais forte passa a ser defeito ou degradação da própria mídia `SG0R26`.
- A última tentativa segura usando o índice em disco também foi executada: o catálogo local preservou 152402 entradas (~201.4 GB lógicos) da `SG0R26`, e foi gerado um bundle de recuperação com manifesto e evidências em `/mnt/raid1/ltfs-cat-backups/sg0r26-recovery-*`.
- Mesmo com a geração conhecida (`Gen 10`) e o UUID preservado em disco, `ltfsck --capture-index -g 10` continuou falhando antes do mount por não conseguir ler o ANSI label no início da fita.
- Quando a nova fita chegar, o próximo passo é remover a dependência de um único device fixo e tratar `sg0` apenas depois de nova investigação física ou troca de mídia.
