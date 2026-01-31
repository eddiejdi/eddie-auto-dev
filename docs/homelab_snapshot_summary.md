Resumo do snapshot e configuração do homelab (rpa4all)

Contexto:
- Objetivo: garantir que `www.rpa4all.com` funcione e criar snapshot de recuperação de emergência.
- Host principal: homelab (192.168.15.2).

Estado técnico (resumo):
- DNS: Zona em Cloudflare (zone id c9f221b503aff614b2d5fb4e8f365725). MX do Google Workspace preservados.
- TLS/ACME: certs gerados por `acme.sh` (DNS-01 via Cloudflare) e instalados em `/home/homelab/.acme.sh/rpa4all.com_ecc/` (fullchain.cer, key).
- Nginx: vhost `www.rpa4all.com` configurado para usar os certificados ACME.

Cloudflare Tunnel:
- Tunnel nomeado: `rpa4all-tunnel` (id: `8169b9cd-a798-4610-b3a6-ed7218f6685d`).
- Credentials: `/home/homelab/.cloudflared/8169b9cd-....json`.
- Origin cert: `/home/homelab/.cloudflared/cert.pem`.
- Systemd unit: `cloudflared-rpa4all.service` configurada para usar `--origin-server-name` para evitar mismatch TLS.
- DNS: `www.rpa4all.com` CNAME apontando para `<tunnel-id>.cfargotunnel.com`.

Snapshot & Backup (rsync-based):
- Script: `scripts/create_snapshot.sh` (deployed em `/usr/local/bin/create_snapshot.sh`).
  - Recursos: verificação de espaço, lock, gravação atômica em temp dir, retenção por dias/contagem, DRY_RUN.
- Local destino: `/mnt/storage/backups` (montado a partir de `/dev/sda3` via LVM; ~135G livre após limpeza de snapshots).
- Snapshots criados (exemplos):
  - `/mnt/storage/backups/rpa4all-snapshot-20260131T021745Z`
  - `/mnt/storage/backups/rpa4all-snapshot-20260131T024533Z`
  - `/mnt/storage/backups/rpa4all-snapshot-20260131T032601Z` (inclui `/boot` e `/boot/efi`).
- Serviço timer: `rpa4all-snapshot.timer` + `rpa4all-snapshot.service` (OnCalendar=daily).
- Log: `/var/log/create_snapshot.log` (logrotate configurado).

Restauração testada (procedimento resumido):
- Criação de imagem de teste (loopback) e restauração do snapshot via `rsync -aAX --numeric-ids`.
- Chroot e execução de `update-initramfs` e `grub-mkconfig` para validar que `/boot` e ESP são suficientes para gerar `grub.cfg`.
- Documentação de restauração: `scripts/RESTORE.md` (passos para chroot, reinstalar GRUB, etc.).

Notas/ações recomendadas:
- Copiar snapshots offsite (S3/rsync remoto) para redundância.
- Automatizar teste de restauração periódico.
- Considerar snapshots LVM se houver espaço disponível no PV ou adicionando disco.

Referências locais relevantes:
- `scripts/create_snapshot.sh`
- `scripts/RESTORE.md`
- `/etc/systemd/system/rpa4all-snapshot.service` and `.timer`
- `/etc/cloudflared/config.yml`
- `/etc/nginx/sites-available/www.rpa4all.com`
- `/var/log/create_snapshot.log`

Indexado em: $(date -u +%Y-%m-%dT%H:%M:%SZ)
