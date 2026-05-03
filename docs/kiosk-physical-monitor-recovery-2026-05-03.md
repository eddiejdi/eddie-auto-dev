# Recuperação do Kiosk físico — Monitor HDMI onboard (Intel) — 2026-05-03

Resumo rápido
----------------
- Problema: monitor físico (:0 vt1) não estava mostrando Grafana — Xorg preso em D-state durante inicialização.
- Ação tomada: diagnóstico, ajuste de configuração Xorg, reinício controlado do ciclo físico (`xinit`/`Xorg`) sem matar o controlador `tty1-wrapper`, validação com `surf` exibindo Grafana.

Objetivo deste documento
-------------------------
Documentar todos os caminhos, comandos e artefatos usados para a recuperação, para evitar redescobertas futuras. Incluir arquivos alterados, backups, comandos de intervenção e passos de rollback.

Hardware / contexto
--------------------
- Servidor homelab: Intel i9-9900T (8 cores × HT = 16 vCPUs)
- GPU de vídeo primária para monitor físico: Intel UHD 630 (onboard) — `PCI:0:2:0` (/dev/dri/card2)
- `tty1-wrapper` controla o ciclo do kiosk físico: `/usr/local/bin/tty1-wrapper` (rodando como child PID 1)
- Kiosk virtual (Xvfb :99) separado: `kiosk-dashboard.service` (Chrome lean mode)

Problema observado
-------------------
- Xorg :0 travando em estado D (I/O sleep) durante a enumeração de devices (onde udev adiciona muitos `/dev/input/event*`).
- Logs mostravam repetidas linhas `config/udev: Adding input device ...` e (antes da correção) tentativas de usar glamor/DRI.

Diagnóstico (resumo)
---------------------
- Stack do processo Xorg mostrou `folio_wait_bit_common` (espera em I/O de memória compartilhada).
- Falha ao carregar `libinput` inicialmente (warning no log), e enumeração de muitos devices aumentou o tempo.
- Decisão: evitar glamor/DRI e evitar AutoAdd de devices para acelerar inicializações do Xorg no kiosk físico.

Ações executadas (cronológico, comandos principais)
--------------------------------------------------
1. Verificação de configs e logs

```bash
sudo tail -n4 /var/log/Xorg.0.log
ls /etc/X11/xorg.conf.d/
sudo cat /etc/X11/xorg.conf.d/10-intel-kiosk.conf
ps -eo pid,ppid,stat,comm | egrep "xinit|Xorg|tty1-wrapper|surf"
```

2. Adição temporária para acelerar diagnósticos (ex.: `AutoAddDevices`)

```bash
sudo sed -i '/Section "ServerFlags"/a\    Option         "AutoAddDevices" "false"' /etc/X11/xorg.conf.d/10-intel-kiosk.conf
```

3. Substituição final do `10-intel-kiosk.conf` (definição final usada)

Conteúdo final do arquivo (exato):

```text
# Force Xorg to use Intel UHD 630 onboard (free NVIDIA GPUs for compute)
Section "ServerLayout"
    Identifier     "KioskLayout"
    Screen         "IntelScreen"
EndSection

Section "Device"
    Identifier     "IntelGPU"
    Driver         "modesetting"
    BusID          "PCI:0:2:0"
    Option         "AccelMethod" "none"
EndSection

Section "Screen"
    Identifier     "IntelScreen"
    Device         "IntelGPU"
    DefaultDepth   24
    SubSection     "Display"
        Depth      24
    EndSubSection
EndSection

Section "ServerFlags"
    Option         "AutoAddGPU"     "false"
    Option         "AutoBindGPU"    "false"
    Option         "AutoAddDevices" "false"
EndSection
```

Backup criado automaticamente (exemplo):

```
/etc/X11/xorg.conf.d/10-intel-kiosk.conf.bak-20260503T140356Z
```

4. Reinício controlado do ciclo físico (não matar `tty1-wrapper`)

Passos usados (seguros):

```bash
# Remover processos X problemáticos (apenas xinit/Xorg, NÃO matar tty1-wrapper):
sudo pgrep -f "Xorg :0 vt1" | xargs -r sudo kill -KILL
sudo pgrep -f "xinit /tmp/xinitrc-kiosk" | xargs -r sudo kill -KILL
sudo rm -f /tmp/.X0-lock /tmp/.X11-unix/X0

# Aguarde o tty1-wrapper relançar o xinit (ele roda em loop e relançará):
pgrep -af "xinit /tmp/xinitrc-kiosk"

# Verificar se o navegador surf iniciou na sessão física:
pgrep -a surf
```

Observação: no diagnóstico real os comandos de `kill` precisaram respeitar múltiplos PIDs; usar `pgrep | xargs` é mais robusto que passar listas multiline para `kill`.

5. Validação final

- `ps` mostrou `surf` rodando com o URL do dashboard local: `http://localhost:3002/d/homelab-btop/homelab-system-monitor-btop?kiosk&refresh=30s`.
- `/var/log/Xorg.0.log` mostrou `modeset(0): Output HDMI-3 connected` e `AutoAddDevices is off - not adding device.`

Snippets de log relevantes
-------------------------
```text
[ 79285.236] (II) modeset(0): Output HDMI-3 connected
[ 79285.236] (II) modeset(0): Output HDMI-3 using initial mode 1920x1080 +0+0

[ 79340.980] (II) config/udev: Adding input device HDA NVidia HDMI/DP,pcm=8 (/dev/input/event14)
[ 79340.980] (II) AutoAddDevices is off - not adding device.
```

Arquivos alterados e backups
----------------------------
- `/etc/X11/xorg.conf.d/10-intel-kiosk.conf`
  - Backup: `/etc/X11/xorg.conf.d/10-intel-kiosk.conf.bak-20260503T140356Z`
  - Motivo: desabilitar glamor/DRI (`AccelMethod none`) e evitar AutoAddDevices para acelerar boot do X

- `/usr/local/bin/tty1-wrapper` (controlador do kiosk físico) — NÃO alterado; **NÃO** matar este processo manualmente

- `/opt/kiosk-dashboard/start-kiosk.sh` (kiosk virtual Xvfb :99) — já estava modificado para Chrome lean mode
  - Backup: `/opt/kiosk-dashboard/start-kiosk.sh.bak-20260503`

- `/opt/kiosk-dashboard/index.html` — reduzido refresh e animações; backup: `/opt/kiosk-dashboard/index.html.bak-20260503`

Comandos úteis para troubleshooting futuro
-----------------------------------------
- Ver logs Xorg em tempo real:

```bash
sudo tail -n200 -f /var/log/Xorg.0.log
```

- Verificar processos do kiosk físico:

```bash
ps -eo pid,ppid,pcpu,stat,comm,args | egrep "tty1-wrapper|xinit|Xorg|xinitrc|surf" | grep -v grep
```

- Reiniciar ciclo físico (seguro):

```bash
sudo pgrep -f "Xorg :0 vt1" | xargs -r sudo kill -KILL
sudo pgrep -f "xinit /tmp/xinitrc-kiosk" | xargs -r sudo kill -KILL
sudo rm -f /tmp/.X0-lock /tmp/.X11-unix/X0
# aguardar tty1-wrapper relançar (ele roda em loop):
pgrep -af "xinit /tmp/xinitrc-kiosk"
```

Rollback (restaurar config anterior)
-----------------------------------

```bash
sudo cp -a /etc/X11/xorg.conf.d/10-intel-kiosk.conf.bak-20260503T140356Z /etc/X11/xorg.conf.d/10-intel-kiosk.conf
# depois reiniciar o ciclo como acima (kill xinit/Xorg) para aplicar
```

Recomendações e observações
---------------------------
- Nunca matar `tty1-wrapper`; ele é o controlador do display físico. Mate apenas `xinit`/`Xorg` quando necessário.
- Para kiosks físicos com GPU onboard, preferir `AccelMethod none` para evitar deadlocks relacionados a GL/DRI quando a máquina tem carga alta.
- `AutoAddDevices` desativado reduz o tempo de inicialização quando há muitos `/dev/input/event*` no sistema.
- Registrar backups com timestamp (já automatizado nos passos acima).

Checklist rápida para o próximo incidente
---------------------------------------
1. Checar `/var/log/Xorg.0.log` e `ps` (xinit/Xorg)
2. Se Xorg em D-state por I/O, aplicar `AccelMethod none` + `AutoAddDevices false` temporariamente
3. Kill xinit/Xorg (não o `tty1-wrapper`) e remover `/.X0-lock`
4. Verificar `surf` e dashboards

Sugestão de título para Wiki e tags
----------------------------------
- Título: `Kiosk: Recuperação Monitor Físico (Intel onboard) - 2026-05-03`
- Tags: `homelab`, `kiosk`, `xorg`, `grafana`, `intel-igpu`

---
Documento gerado automaticamente pelo operador (registro das ações do dia). Se quiser que eu também anexe extratos de log completos ou screenshots ao criar a página na Wiki, diga quais arquivos anexar.
