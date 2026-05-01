# LTFS Drain Urgente - Deploy e Validacao

Data: 2026-04-27
Escopo: aplicar exclusao por arquivo apos transferencia validada no drain para LTFS, com deploy imediato em producao.

## Objetivo

Trocar o comportamento de limpeza da origem de lote inteiro para exclusao progressiva por arquivo, reduzindo uso do NVMe durante a copia.

## Mudanca aplicada no script

Arquivo de execucao no NAS: `/tmp/drain_buffer_v2.sh`

Alteracao principal no rsync:

- Antes: `--delete-after`
- Depois: `--remove-source-files --prune-empty-dirs`

Flags mantidas para LTFS:

- `--whole-file`
- `--no-partial`
- `--timeout=300`

## Deploy executado

1. Copia do script atualizado para jump host.
2. Copia do jump host para NAS.
3. Interrupcao do drain antigo e rsyncs antigos desse job.
4. Start imediato do novo drain em background (`nohup bash /tmp/drain_buffer_v2.sh`).
5. Validacao em runtime do comando rsync ativo e das contagens origem/destino.

## Evidencias de validacao

### Processo ativo com nova flag

Rsync em execucao no NAS:

`rsync ... --remove-source-files --prune-empty-dirs ...`

### Efeito real observado

Snapshot de validacao apos deploy:

- `SRC_FILES=861`
- `DST_FILES=133`
- `df /`: `/dev/nvme0n1p2 229G 189G 29G 87% /`

Interpretacao:

- A origem esta reduzindo durante a transferencia (exclusao por arquivo ativa).
- O NVMe ja caiu de 88% para 87% no periodo de validacao.

## Impacto operacional

- Espaco passa a ser liberado progressivamente durante o drain.
- Evita esperar o final do lote para ver queda no painel.
- Mantem padrao seguro para LTFS (sem append-verify e sem partial).

## Comandos de monitoramento rapido

```bash
ssh homelab@192.168.15.2 'ssh root@192.168.15.4 "
pgrep -af '^bash /tmp/drain_buffer_v2.sh$|rsync .*nvme-offload-20260427' || true
SRC='/srv/nextcloud/data/edenilson.paschoa@rpa4all.com/files/UploadInstantâneo.bak.223225'
DST='/mnt/tape/lto6/nvme-offload-20260427/nextcloud/edenilson/UploadInstantaneo_bak'
[[ -d \"$SRC\" ]] && echo SRC_FILES=$(find \"$SRC\" -type f | wc -l)
[[ -d \"$DST\" ]] && echo DST_FILES=$(find \"$DST\" -type f | wc -l)
df -h / | tail -1
"'
```

## Status

- Deploy em producao: CONCLUIDO
- Validacao de efeito: CONCLUIDA
- Wiki: pendente de publicacao desta mesma documentacao
- GitHub: pendente de commit/push desta documentacao
