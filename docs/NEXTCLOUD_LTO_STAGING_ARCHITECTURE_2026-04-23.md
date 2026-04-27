# Padrao operacional: Nextcloud -> staging -> LTFS

Data: 2026-04-23

## Contrato

O Nextcloud nao deve gravar diretamente na fita LTFS.

O caminho `/LTO` do Nextcloud e uma area de staging em disco, compartilhada por todos os usuarios autorizados no Nextcloud. A fita e destino de arquivamento, nao filesystem online multiusuario.

## Invariantes obrigatorias

- `/LTO` no Nextcloud aponta para staging em disco: `/mnt/raid1/lto6-cache`, exposto ao container por `/mnt/lto6-nc -> /var/www/html/external/LTO`.
- O storage externo `/LTO` permanece aplicavel a `All` no Nextcloud.
- O usuario efetivo de escrita do Nextcloud e `www-data` (`uid=33`, `gid=33`), portanto o staging deve aceitar escrita desse usuario.
- Somente o worker `ltfs-cache-flush.service` pode copiar dados do staging para alvos LTFS reais.
- O worker deve operar serializado por lock (`/run/ltfs-cache-flush.lock`) e nunca em paralelo.
- A fita deve ser usada em janelas controladas: montar, copiar arquivos estaveis, fazer `sync`, verificar, atualizar catalogo e desmontar limpo.
- A LTFS nao deve ser bind-mounted dentro de `/srv/nextcloud/external/LTO`, `/home/homelab/nextcloud/external_local/LTO` ou diretorios pessoais de usuarios.
- Qualquer compatibilidade para upload automatico de celular deve cair no staging, nunca direto em LTFS.

## Motivo

LTFS nao e um backend seguro para escrita online multiusuario. Uploads Android e WebDAV geram arquivos temporarios, renames, chunks e fechamentos parciais. Se isso aciona LTFS diretamente, uma queda de rede, restart de container, remount ou timeout pode impedir o fechamento correto de EOD/indice da fita.

O erro observado no NAS foi:

- `EOD of DP(1) is missing`
- `Medium revalidation failed`
- `Data partition writer: failed to write data to the tape`

Esse padrao indica que a fita estava em ciclo de escrita e o LTFS nao conseguiu finalizar corretamente o fim de dados.

## Estado validado em 2026-04-23

- O Nextcloud lista `/LTO` como storage externo aplicavel a `All`.
- O container `nextcloud-app` monta `/mnt/lto6-nc` em `/var/www/html/external/LTO`.
- A escrita como `www-data` em `/var/www/html/external/LTO` foi validada com arquivo temporario.
- O staging atual tem permissao `uid=33`, `gid=33`, modo `770`.
- A fita `HUJ548` entrou em `ltfsck --deep-recovery /dev/sg0` apos erro de EOD ausente.
- O homelab foi ajustado para persistir `/mnt/raid1/lto6-cache -> /mnt/lto6-nc`.
- O timer `lto-logical-mount-refresh.timer` foi desativado para nao montar fita fora do worker.
- `ltfs-cache-flush` foi ajustado para considerar somente arquivos maduros (`MIN_AGE_SECONDS=900`, `MIN_STABLE_SECONDS=300`).

## Padrao de montagem

No homelab:

```fstab
# Nextcloud /LTO e staging em disco, nao LTFS.
/mnt/raid1/lto6-cache /mnt/lto6-nc none bind 0 0
```

Nao usar:

```fstab
192.168.15.4:/mnt/tape/lto6 /mnt/lto6-nc nfs4 ...
```

No NAS:

- Manter LTFS em `/mnt/tape/lto6` apenas para o worker de arquivamento.
- Nao fazer bind de `/mnt/tape/lto6` ou `/run/ltfs-export/lto6` para `/srv/nextcloud/external/LTO`.
- Se `/mnt/tape/lto6` for exportado por NFS/SMB, o consumidor deve ser o worker de flush, nao o Nextcloud.

## Systemd esperado no homelab

`lto-logical-mount-refresh.timer` deve ficar desativado. Ele cria uma visao logica que tenta montar branches de fita e nao deve participar do caminho online do Nextcloud.

`ltfs-cache-flush.service` deve ser o unico escritor de fita. Ele mantem `ExecStartPre=/usr/local/bin/lto-ensure-nas-mounts`, usa lock proprio e executa `sync` apos o flush.

`ltfs-cache-flush.timer` deve usar janela em lote, nao polling de 15 segundos. O padrao desejado e `OnCalendar=*:0/30` com `AccuracySec=1min`.

## Fluxo correto

1. Usuario grava em `/LTO` pelo Nextcloud.
2. Arquivo fica no staging em disco.
3. `ltfs-cache-flush.service` identifica arquivos completos e estaveis.
4. O worker copia para LTFS real em modo serializado.
5. O worker valida tamanho/catalogo e registra `placements.json`/`catalog.jsonl`.
6. A fita recebe `sync` e deve ser desmontada limpidamente ao fim da janela.

## Comandos de verificacao

Validar que o Nextcloud grava no staging:

```bash
docker exec -u www-data nextcloud-app sh -lc 'p=/var/www/html/external/LTO/.probe; date > "$p"; stat "$p"; rm -f "$p"'
```

Validar storage externo:

```bash
docker exec nextcloud-app php occ files_external:list
```

Validar worker:

```bash
systemctl status ltfs-cache-flush.service ltfs-cache-flush.timer
journalctl -u ltfs-cache-flush.service -n 100 --no-pager
```

Validar catalogo:

```bash
tail -n 20 /var/lib/ltfs-cache-flush/catalog.jsonl
```

## Proibicoes operacionais

- Nao apontar `/var/www/html/external/LTO` diretamente para NFS/SMB/FUSE LTFS.
- Nao expor LTFS como pasta pessoal de usuario Nextcloud.
- Nao rodar multiplos flushes concorrentes.
- Nao matar `ltfs`, `ltfsck` ou desmontar FUSE durante escrita/recovery.
- Nao reiniciar NAS/homelab durante escrita LTFS sem stop limpo do servico.
