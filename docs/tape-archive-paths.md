# Tape Archive Paths

Este documento consolida o fluxo de gravação para o mountpoint da fita usado no homelab.

## Estado operacional

- Mountpoint principal: `/mnt/tape_sg0`
- Origem atual do mountpoint: bind mount de `/mnt/lto6`
- Origem funcional de `/mnt/lto6`: compartilhamento CIFS `//192.168.15.4/LTO6`
- Diretório de logs da fita: `/mnt/tape_sg0/logs`
- Diretório de ISOs da fita: `/mnt/tape_sg0/isos`

## Objetivo

Guardar artefatos grandes diretamente no mountpoint da fita para liberar espaço no root e centralizar a retenção de:

- backups de catálogo LTFS
- imagens ISO geradas localmente
- logs operacionais dos fluxos de fita

## Fluxo de escrita

### ISOs

Os scripts de geração de ISO agora gravam o resultado final no root da fita antes de qualquer cópia opcional para Ventoy.

Arquivos envolvidos:

- [create_live_iso_from_host.sh](../create_live_iso_from_host.sh)
- [create_live_iso_from_snapshot.sh](../create_live_iso_from_snapshot.sh)

Comportamento:

- `TAPE_ARCHIVE_ROOT` padrão: `/mnt/tape_sg0`
- `ISO_OUTPUT_DIR` padrão: `$TAPE_ARCHIVE_ROOT/isos`
- `LOG_DIR` padrão: `$TAPE_ARCHIVE_ROOT/logs`
- a ISO final é copiada para `ISO_OUTPUT_DIR`
- se Ventoy estiver montado, uma cópia adicional ainda pode ser feita para o USB

### Logs LTFS

Os logs operacionais do catálogo e dos remounts usam o mountpoint da fita como destino primário.

Arquivos envolvidos:

- [tools/ltfs_backup_catalog.sh](../tools/ltfs_backup_catalog.sh)
- [tools/ltfs-trigger-homelab-remount.sh](../tools/ltfs-trigger-homelab-remount.sh)
- [tools/ltfs-nfs-remount.sh](../tools/ltfs-nfs-remount.sh)
- [tools/ltfs-selfheal-remount.sh](../tools/ltfs-selfheal-remount.sh)

Comportamento:

- `TAPE_ARCHIVE_ROOT` padrão: `/mnt/tape_sg0`
- `LTFS_LOG_DIR` ou `TAPE_LOG_ROOT` apontam para `$TAPE_ARCHIVE_ROOT/logs`
- fallback para `/var/log` só acontece se o mountpoint não existir ou não estiver gravável

## Variáveis de ambiente

As principais variáveis agora são:

- `TAPE_ARCHIVE_ROOT=/mnt/tape_sg0`
- `ISO_OUTPUT_DIR=$TAPE_ARCHIVE_ROOT/isos`
- `LOG_DIR=$TAPE_ARCHIVE_ROOT/logs`
- `LTFS_LOG_DIR=$TAPE_ARCHIVE_ROOT/logs`
- `TAPE_LOG_ROOT=$TAPE_ARCHIVE_ROOT/logs`

Esses valores podem ser sobrescritos no shell ou em units systemd, mas o padrão operacional deve permanecer no mountpoint da fita.

## Diretrizes de uso

1. Gravar ISOs grandes em `/mnt/tape_sg0/isos`.
2. Gravar logs operacionais de fita em `/mnt/tape_sg0/logs`.
3. Manter `/var/log` apenas como fallback de emergência.
4. Não usar o root do sistema como destino final para artefatos grandes de fita.

## Arquivos afetados

- [create_live_iso_from_host.sh](../create_live_iso_from_host.sh)
- [create_live_iso_from_snapshot.sh](../create_live_iso_from_snapshot.sh)
- [tools/ltfs_backup_catalog.sh](../tools/ltfs_backup_catalog.sh)
- [tools/ltfs-trigger-homelab-remount.sh](../tools/ltfs-trigger-homelab-remount.sh)
- [tools/ltfs-nfs-remount.sh](../tools/ltfs-nfs-remount.sh)
- [tools/ltfs-selfheal-remount.sh](../tools/ltfs-selfheal-remount.sh)
- [tests/test_tape_archive_paths.py](../tests/test_tape_archive_paths.py)

## Validação

Validações executadas após a mudança:

- `pytest -q tests/test_tape_archive_paths.py`
- `bash -n` nos scripts alterados
- checagem de referências para confirmar que os caminhos novos apontam para `/mnt/tape_sg0`

## Observação operacional

O mountpoint atual está disponível como bind de `/mnt/lto6`, então qualquer artefato gravado em `/mnt/tape_sg0` segue para o caminho ativo da fita exposta no homelab.
