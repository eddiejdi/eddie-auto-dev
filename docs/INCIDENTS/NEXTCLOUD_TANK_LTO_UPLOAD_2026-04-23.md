# Incidente: Nextcloud Android TANK e trilha LTO

Data: 2026-04-23

## Resumo

O TANK (`192.168.15.150`, `tank3-pro`) voltou a receber DHCP corretamente, mas os uploads Android para o Nextcloud ainda nao estavam sendo materializados em arquivo. A trilha de fita tambem nao estava gravando no LTO real no momento da verificacao.

Correcao de arquitetura definida em seguida: `/LTO` no Nextcloud deve ser staging em disco para todos os usuarios; somente um worker controlado pode gravar na fita LTFS real.

## Estado encontrado

- O cliente Android estava chamando WebDAV em `UploadInstantaneo` com `remoteAddr=192.168.15.150`.
- O Nextcloud bloqueava o TANK por brute-force (`TooManyRequests`), com atraso de 25s antes da limpeza.
- A conta `edenilson.paschoa@rpa4all.com` existia e estava habilitada, mas o diretorio fisico em `/var/www/html/data/edenilson.paschoa@rpa4all.com` nao existia no volume ativo.
- O mount externo `/LTO` apontava para `/mnt/lto6-nc`.
- A tentativa anterior de tratar `/mnt/lto6-nc` como fita real estava incorreta: no estado funcional ele deve ser staging em disco, nao a LTFS.
- O NAS `192.168.15.4` exportava `/mnt/tape/lto6`, mas:
  - NFSv4 para `/mnt/tape/lto6` retornou `Input/output error`.
  - NFSv3 retornou `Permission denied`.
  - CIFS `//192.168.15.4/LTO6` retornou `NT_STATUS_ACCESS_DENIED`.
  - CIFS `//192.168.15.4/LTO6_CACHE` retornou `NT_STATUS_BAD_NETWORK_NAME`.

## Acoes executadas

- Adicionado `192.168.15.150/32` a allowlist de brute-force do Nextcloud (`bruteForce whitelist_1`).
- Resetado o contador de brute-force do TANK.
- Recriados os diretorios minimos da conta Edenilson no data directory ativo:
  - `/home/homelab/nextcloud/data_local/edenilson.paschoa@rpa4all.com`
  - `files/`
  - `cache/`
  - `files/UploadInstantaneo`
- Recriado `/home/homelab/nextcloud/external_local/RPA4ALL` para remover erro de storage externo ausente.
- Redirecionado `/mnt/lto6-nc` para o staging local (`/mnt/raid1/lto6-cache`) via bind mount.
- Reiniciado `nextcloud-app` para o container enxergar `/var/www/html/external/LTO` como `mergerfs[/lto6-cache]`.
- Ativado `nc-upload-lto-bind.service`, deixando `UploadInstantaneo` da conta montado sobre o cache LTFS local.
- Validada escrita no caminho montado como `www-data`.
- Confirmado que o storage externo `/LTO` esta aplicavel a `All` no Nextcloud.
- Confirmado que o NAS/LTFS entrou em erro `EOD of DP(1) is missing` e exigiu `ltfsck --deep-recovery`.
- Iniciado `ltfsck --deep-recovery /dev/sg0` na fita `HUJ548`.

## Estado atual

- `/LTO` grava no staging local, nao diretamente em fita.
- Esse e o padrao correto: Nextcloud escreve em staging; o worker `ltfs-cache-flush` grava a fita.
- `/etc/fstab` do homelab foi ajustado para desativar `192.168.15.4:/mnt/tape/lto6 -> /mnt/lto6-nc` e persistir `/mnt/raid1/lto6-cache -> /mnt/lto6-nc`.
- Escrita como `www-data` no container foi validada em `/var/www/html/external/LTO`.
- `lto-logical-mount-refresh.timer` foi desativado para parar tentativas automaticas de montar `/mnt/lto6`.
- `ltfs-cache-flush` foi ajustado para aceitar somente arquivos com `MIN_AGE_SECONDS=900` e `MIN_STABLE_SECONDS=300`.
- O servico `nc-upload-lto-bind.service` esta ativo.
- O TANK esta na allowlist de brute-force e sem atraso (`attempts=0`, `delay=0`).
- A fita fisica ainda nao foi validada como destino de gravacao apos recovery; o `ltfsck` estava em andamento.
- A LAN desta estacao oscilou: `enp0s31f6` ficou sem ARP funcional para `192.168.15.0/24`; o acesso ao homelab foi possivel temporariamente via `wlp2s0` usando `socat`, mas a Wi-Fi depois saiu para `192.168.0.0/24`.

## Proximos passos

1. Aguardar o fim do `ltfsck --deep-recovery /dev/sg0`.
2. Remover no NAS o bind automatico de LTFS para `/srv/nextcloud/external/LTO`.
3. Verificar se o override do timer `ltfs-cache-flush.timer` ficou com `OnCalendar=*:0/30` apos a queda de SSH.
4. Executar um flush controlado do staging para LTFS real.
5. Validar `catalog.jsonl`, `placements.json` e leitura direta da fita apos remount limpo.
6. Confirmar que o NAS nao exporta a fita para uso direto do Nextcloud.

## Padrao fixado

Ver tambem: `docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md`.
