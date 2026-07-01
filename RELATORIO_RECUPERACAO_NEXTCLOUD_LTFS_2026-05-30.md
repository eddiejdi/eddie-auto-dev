# Relatorio Consolidado de Recuperacao - Nextcloud + LTFS

Data: 2026-05-30

## 1) Escopo e objetivo

Este relatorio consolida toda a atuacao realizada para:

1. Reabilitar o Nextcloud no homelab.
2. Garantir escrita no caminho de dados correto (NAS/NFS).
3. Recuperar espaco em disco ate sair de estado critico.
4. Restaurar o pipeline LTFS (mount + flush) para evitar novo enchimento.

## 2) Ambiente envolvido

1. Nextcloud em container Docker (`nextcloud:latest`, app `33.0.0.16`).
2. Dados do Nextcloud via NFS para `:/srv/nextcloud/data` no NAS (`192.168.15.4`).
3. Pipeline de fita LTFS no NAS com `tape-manager` e services/timers de flush.

## 3) Sintomas iniciais observados

1. Nextcloud com problemas de montagem/configuracao apos recriacao do container.
2. Volume de dados em 100% e operacao degradada por `No space left on device`.
3. Divergencia entre `df` (alto uso) e alguns levantamentos parciais de `du`.
4. `ltfs-cache-flush.service` falhando com mensagens de read-only no caminho LTFS.

## 4) Causa raiz (consolidada)

Foram encontradas causas combinadas:

1. Acumulo critico no cache de spool de fita no NAS:
   - ` /var/spool/lto6-cache/backups/rpa4all-snapshot-20260502T100642Z` com ~52G.
2. Falha de sync da fita LTFS, gerando comportamento efetivo de somente leitura e falha de flush.
3. Inconsistencia de indice LTFS na midia `SG0001`, exigindo recuperacao profunda (`deep-recovery`).
4. Em etapa posterior, concorrencia de flush (mais de um processo), causando erros `ENOENT` durante copia.

## 5) Acoes executadas (ordem logica)

## 5.1 Nextcloud / NFS

1. Recriacao do container com bind correto do diretorio de dados NFS.
2. Reposicao explicita do bind de config (`/var/www/html/config`) para eliminar 503.
3. Validacao de health da aplicacao via `occ status` e endpoint HTTP.

## 5.2 Limpezas seguras no Nextcloud

1. Execucao de `trashbin` / `versions` / `preview` cleanups (com impacto limitado).
2. Quarentena de uploads obsoletos sem delecao destrutiva.
3. Zerar `nextcloud.log` quando identificado como candidato.

## 5.3 Recuperacao de espaco no NAS

1. Diagnostico direto no NAS para evitar latencia/ambiguidade do caminho NFS no cliente.
2. Identificacao e remocao do snapshot gigante preso no spool LTFS (`~52G`).
3. Validacao imediata de espaco livre apos limpeza do cache.

## 5.4 Recuperacao LTFS

1. Diagnostico de falha de mount/sync LTFS com logs (`MODESELECT`, `XML parser`, `extra blocks detected`).
2. `ltfs_recovery.py --deep-recovery` executado com sucesso funcional de recuperacao de consistencia:
   - reconstrucao de indice para geracao `38`.
   - volume reportado consistente pelo fluxo de recovery.
3. `ltfs_recovery.py --orchestrated-mount` aplicado e mount restabelecido em `rw`.
4. Teste de escrita real no mount LTFS concluido com sucesso (`WRITE_OK`).
5. Reativacao de timers/servicos LTFS para continuidade automatica do pipeline.

## 6) Validacoes de estado (snapshot final)

Coleta em 2026-05-30 por volta de 21:13:

1. Nextcloud host mount:
   - `229G total / 176G usado / 42G livre / 82%`.
2. Nextcloud no container (`/var/www/html/data`):
   - `229G total / 176G usado / 42G livre / 82%`.
3. NAS raiz (`/`):
   - `229G total / 177G usado / 42G livre / 82%`.
4. LTFS:
   - mount ativo em `/mnt/tape/lto6` com opcoes `rw`.
5. Services/timers LTFS:
   - `ltfs-lto6.service` ativo.
   - `ltfs-cache-flush.timer` ativo.
   - `ltfs-idle-unmount.timer` ativo.
   - `lto6-selfheal.timer` ativo.
6. Spool atual:
   - `~27G` em `/var/spool/lto6-cache` (em drenagem ativa).

## 7) Pontos de atencao e riscos residuais

1. Durante o flush em alta concorrencia, houve eventos `ENOENT` para alguns arquivos no spool.
   - Sintoma compativel com corrida entre processos de flush na mesma fila.
2. E necessario garantir no operacional:
   - somente um processo de `tape-manager flush` por vez.
3. O sistema saiu do estado critico de disco cheio, mas o spool ainda esta em drenagem.

## 8) Recomendacoes operacionais

1. Manter monitoramento de:
   - `/var/spool/lto6-cache` (tendencia de queda).
   - estado dos timers LTFS.
   - mount LTFS `rw`.
2. Criar trava explicita anti-concorrencia no comando de flush (se ainda nao existir internamente).
3. Configurar alerta de capacidade para:
   - spool LTFS (`70/80/90%` por thresholds).
   - filesystem raiz do NAS.

## 9) Comandos uteis de verificacao rapida

```bash
# Homelab/Nextcloud
ssh -o BatchMode=yes homelab 'sudo bash -lc "df -h /mnt/disk1/docker/volumes/nc-nas-data/_data; docker exec nextcloud-app df -h /var/www/html/data"'

# NAS - espaco e spool
ssh -o BatchMode=yes homelab "ssh -o BatchMode=yes 192.168.15.4 'sudo -n bash -lc \"df -h /; du -sh /var/spool/lto6-cache /var/spool/lto6-cache/backups\"'"

# NAS - LTFS services e mount
ssh -o BatchMode=yes homelab "ssh -o BatchMode=yes 192.168.15.4 'sudo -n bash -lc \"systemctl is-active ltfs-lto6.service ltfs-cache-flush.timer ltfs-idle-unmount.timer lto6-selfheal.timer; findmnt -T /mnt/tape/lto6 -o TARGET,SOURCE,FSTYPE,OPTIONS\"'"
```

## 10) Resultado final

1. Nextcloud reabilitado e funcional.
2. Escrita no caminho correto NFS/NAS confirmada.
3. Disco saiu de estado critico (0 disponivel) para margem operacional.
4. Pipeline LTFS recuperado, montado em `rw` e com flush novamente funcional.
