# LTFS Journal Replication — Variáveis

Serviço: `ltfs-journal-replicate.service` + `.timer` (systemd), script
`tools/ltfs_journal_replicate.py`. Replica o journal LTFS
(`/var/lib/ltfs-journal`) para a NAS após cada sessão de flush/drain/checkpoint
(gap G13 do review `docs/NEXTCLOUD_LTO_FLOW_REVIEW_2026-08-02.md`), evitando
perda do journal se o homelab perder o disco local.

| Variável | Default | Propósito |
|---|---|---|
| `LTFS_JOURNAL_DIR` | `/var/lib/ltfs-journal` | Diretório do journal LTFS no disco local (também usado por `ltfs_checkpoint_writer.py`). |
| `JRNL_REPLICA_NAS` | *(obrigatório)* | Destino rsync na NAS, ex.: `rsync://root@192.168.15.4/volume1/ltfs/journal`. Configurado no `Environment=` do serviço. |
| `JRNL_REPLICA_EXTRA` | *(vazio)* | Destino rsync opcional adicional (ex.: mount S3) para segunda cópia. |
| `JRNL_RSYNC_OPTS` | `-a --delete` | Opções do rsync (agregadas com `--timeout=60` sempre). |
| `JRNL_DRY_RUN` | `0` | `1` = só mostra o que seria replicado (rsync `--dry-run`). |

## Consumidor: `ltfs_journal_replicate.py`

O script roda como oneshot `After=ltfs-cache-flush.service` (e drain/checkpoint)
com retry `Restart=on-failure`; o timer (`OnBootSec=5min`, `OnUnitActiveSec=6h`)
cobre sessões que não disparam o oneshot. Exige `rsync` instalado.
