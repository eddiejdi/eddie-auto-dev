# Fluxo Completo LTO - Nextcloud Backup

## Visao Geral

Sistema de backup automatico para Nextcloud usando fitas LTO-6, com montagem NFS para acesso direto.

## Componentes

### 1. NAS (TrueNAS)
- Script de load/eject: /var/db/ltfs-tools/ltfs-flush-eject.sh
- LTFS mount: /mnt/tape/lto6
- NFS export: /mnt/tape/lto6 (rw, no_root_squash)

### 2. Homelab (192.168.15.2)
- Wrapper: /usr/local/bin/ltfs-flush-wrapper.sh
- Flush reverso: /usr/local/bin/ltfs-tape-to-disk.sh
- Monitoramento: /usr/local/bin/ltfs-disk-monitor.sh
- Retencao: /usr/local/bin/ltfs-retention.sh
- NFS mount: /mnt/lto6-tape (uid=33, gid=33)
- NFS mount service: lto6-nfs-mount.service

### 3. Nextcloud
- Container: nextcloud-rpa4all
- External storage: /LTO Backup
- Mount Docker: /mnt/lto6-tape:/var/www/html/external/LTO-Tape

## Fluxo de Trabalho

### Backup (Escrita)
1. Nextcloud grava em disco local (/mnt/lto6-nc -> /mnt/raid1/lto6-cache)
2. Timer ltfs-cache-flush dispara (a cada 30min)
3. load-nas: carrega fita + monta LTFS + monta NFS
4. rsync staging -> /mnt/lto6 (disco local)
5. eject-nas: desmonta NFS + desmonta LTFS + ejecta fita

### Leitura
1. LTFS montado na NAS via load-nas
2. NFS exportado automaticamente
3. Nextcloud acessa via /LTO Backup
4. Apos leitura: eject-nas desmonta tudo

### Flush Reverso (Fita -> Disco)
1. Timer ltfs-tape-to-disk dispara (diario as 03:00)
2. Copia dados da fita para disco local
3. Nextcloud acessa normalmente

## Timers

- ltfs-cache-flush: a cada 30min - Backup disco para fita
- ltfs-tape-to-disk: 03:00 diario - Fita para disco local
- ltfs-disk-monitor: 06/6h - Monitora espaco
- ltfs-retention: Domingo 04:00 - Remove backups antigos

## Comandos Uteis

- Carregar fita: /usr/local/bin/ltfs-flush-wrapper.sh load-nas
- Ejetar fita: /usr/local/bin/ltfs-flush-wrapper.sh eject-nas
- Copiar fita para disco: /usr/local/bin/ltfs-tape-to-disk.sh
- Verificar timers: systemctl list-timers | grep lto6
- Verificar logs: tail -f /var/log/ltfs-cache-flush.log

## Retencao

- Backups mantidos por 30 dias
- Remocao automatica via ltfs-retention.sh
