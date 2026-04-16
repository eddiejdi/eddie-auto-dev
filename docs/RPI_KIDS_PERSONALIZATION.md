# Raspberry Pi Kids Personalization

Fluxo para deixar a ISO `RPi-Desktop-Kids-Atom.iso` mais simples para criancas, seguindo a ideia do artigo do It's FOSS:

- usuario dedicado com login automatico
- apps educacionais na frente (`GCompris`, `Tux Paint`, `Tux Math`, `KLetters`)
- area de trabalho limpa
- icones e painel maiores
- wallpaper mais amigavel
- Chromium com atalhos/bookmarks infantis

## Script

Use [tools/homelab/personalize_rpi_kids_chroot.sh](/workspace/eddie-auto-dev/tools/homelab/personalize_rpi_kids_chroot.sh).

Ele atua sobre um chroot ja extraido, para complementar o remaster existente do homelab.

## Uso no homelab

Aplicar ao build atual:

```bash
scp tools/homelab/personalize_rpi_kids_chroot.sh homelab:/tmp/
ssh homelab 'sudo bash /tmp/personalize_rpi_kids_chroot.sh /var/tmp/rpi-kids-build/chroot'
```

Reempacotar o `filesystem.squashfs` e regenerar a ISO:

```bash
ssh homelab '
  sudo rm -f /var/tmp/rpi-kids-build/isoroot/live/filesystem.squashfs &&
  sudo mksquashfs /var/tmp/rpi-kids-build/chroot /var/tmp/rpi-kids-build/isoroot/live/filesystem.squashfs \
    -comp xz -b 1048576 -Xdict-size 100% \
    -e /var/tmp/rpi-kids-build/chroot/proc \
    -e /var/tmp/rpi-kids-build/chroot/sys \
    -e /var/tmp/rpi-kids-build/chroot/dev \
    -noappend &&
  sudo bash /opt/rpi-kids-post-squashfs.sh
'
```

## Notas

- O wallpaper padrao do script usa `balloon.jpg`, que ja existe na imagem base.
- O painel remove atalhos mais tecnicos para reduzir cliques acidentais.
- O script nao troca a senha nem endurece controles parentais de rede; isso pode ser adicionado depois se voce quiser bloquear dominios ou esconder o navegador por completo.
