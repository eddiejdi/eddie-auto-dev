# Kiosk: Carrossel com 3 Perfis de Trading — 2026-06-20

## Resumo

- Problema 1: carrossel mostrava só Conservative + dashboards tradicionais (Homelab, Akash)
- Problema 2: painéis Grafana não apareciam no carrossel HTML (X-Frame-Options bloqueando iframe)
- Problema 3: página não rolava automaticamente no surf
- Solução: adicionar Aggressive + Shadow no `tty1-wrapper`; habilitar embedding no Grafana; trocar Page Down por mouse wheel scroll

---

## Arquitetura do kiosk (dois sistemas paralelos)

```
Display físico (:0)          Display virtual (:99 — INVISÍVEL ao usuário)
─────────────────────        ────────────────────────────────────────────
homelab-dashboard.service    kiosk-dashboard.service
tty1-wrapper (bash)          start-kiosk.sh (bash)
xinit → Xorg :0 vt1          Xvfb :99 → Chrome
surf (WebKit2GTK)             google-chrome --kiosk
→ URLs Grafana diretas        → http://localhost:8505/ (HTML carousel)
```

**O display físico é controlado pelo `tty1-wrapper`, NÃO pelo Chrome do kiosk-dashboard.service.**

| Caminho | Propósito |
|---------|-----------|
| `/usr/local/bin/tty1-wrapper` | Script bash que controla o display físico |
| `systemd/tty1-wrapper.sh` | Cópia no git (fonte de verdade para alterações) |
| `/opt/kiosk-dashboard/index.html` | HTML carousel (apenas para o Chrome virtual) |
| `web/kiosk-dashboard.html` | Fonte do HTML carousel no git |

---

## Fix 1 — Grafana: habilitar embedding em iframe

**Problema:** `X-Frame-Options: deny` bloqueava os iframes do carrossel HTML.

**Arquivo alterado:** `/home/homelab/docker-compose.grafana.yml`

Variável adicionada:
```yaml
- GF_SECURITY_ALLOW_EMBEDDING=true
```

Cópia sem senha no git: `docker/docker-compose.grafana.yml`

**Para aplicar:**
```bash
cd /home/homelab
docker stop grafana && docker rm grafana
docker-compose -f docker-compose.grafana.yml up -d
```

**Verificar:**
```bash
docker inspect grafana | python3 -c "import json,sys; env=json.load(sys.stdin)[0]['Config']['Env']; [print(e) for e in env if 'EMBED' in e]"
```

---

## Fix 2 — Adicionar perfis Aggressive e Shadow no carrossel físico

**Onde editar:** `systemd/tty1-wrapper.sh` (commit + deploy)

Array `DASHBOARDS` dentro do heredoc `XINIT` (em torno da linha 79):

```bash
DASHBOARDS=(
    "http://localhost:3002/d/homelab-btop/homelab-system-monitor-btop?kiosk&refresh=30s"
    "http://localhost:3002/d/73dbe362-d884-4205-a6c9-24afbd4b03af/akash-network-provider?orgId=1&from=now-3h&to=now&timezone=browser&refresh=30s&kiosk"
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?...&var-profile=conservative&..."
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?...&var-profile=aggressive&..."   ← adicionado
    "http://localhost:3002/d/btc-trading-monitor/f09fa496-trading-agent-monitor?...&var-profile=shadow&..."      ← adicionado
    "http://localhost:3002/d/trading-daily-report-mcp/..."
    "http://localhost:3002/d/storj-node-monitor/..."
)
```

**Para deploy:**
```bash
# 1. Editar systemd/tty1-wrapper.sh no repo
# 2. Copiar para o host
scp systemd/tty1-wrapper.sh homelab@192.168.15.2:/tmp/tty1-wrapper-new.sh
ssh homelab@192.168.15.2 "
  sudo cp /usr/local/bin/tty1-wrapper /usr/local/bin/tty1-wrapper.bak-\$(date +%Y%m%dT%H%M%S)
  sudo cp /tmp/tty1-wrapper-new.sh /usr/local/bin/tty1-wrapper
  sudo chmod +x /usr/local/bin/tty1-wrapper
  sudo systemctl restart homelab-dashboard.service
"
```

**Verificar:**
```bash
ssh homelab@192.168.15.2 "sudo journalctl -t kiosk-rotation -n 5 --no-pager"
# Deve mostrar: Dashboard 1/7, Dashboard 2/7 ...
```

---

## Fix 3 — Scroll automático: mouse wheel em vez de Page Down

**Problema:** `xdotool key Next` (Page Down) não funciona no WebKit2GTK do surf.

**Solução:** `xdotool click 5` (mouse wheel down) após focar a janela e mover o cursor ao centro.

Função no `tty1-wrapper`:
```bash
scroll_down() {
    local surf_pid="$1"
    local win
    win=$(xdotool search --pid "$surf_pid" 2>/dev/null | tail -1)
    [[ -z "$win" ]] && return
    xdotool windowfocus --sync "$win" 2>/dev/null || true
    xdotool mousemove 960 540
    for _ in $(seq 1 "$SCROLL_CLICKS"); do
        xdotool click 5
    done
}
```

Parâmetros atuais:
```bash
SCROLL_CLICKS=15    # cliques wheel por passo
SCROLL_STEPS=6      # passos por dashboard
SCROLL_INTERVAL=15  # segundos entre passos
LOAD_WAIT=12        # segundos de carregamento inicial
BOTTOM_PAUSE=10     # pausa antes de trocar dashboard
```

Tempo total por dashboard: ~12s (load) + 6×15s (scroll) + 10s (pausa) ≈ **112s (~1m52s)**

---

## Dashboard btc-trading-monitor v2

Arquivo: `grafana/dashboards/btc_trading_monitor.json`
- UID: `btc-trading-monitor`
- Versão: 2 (exportado do Grafana em 2026-06-20)
- Variável `?var-profile=`: conservative | aggressive | shadow
- Deploy automático via workflow `deploy-grafana-dashboards.yml` após merge em main

---

## Serviços relevantes

| Serviço | Descrição | Restart |
|---------|-----------|---------|
| `homelab-dashboard.service` | Controla o display físico (tty1-wrapper) | `sudo systemctl restart homelab-dashboard` |
| `kiosk-dashboard.service` | Chrome kiosk no Xvfb virtual | `sudo systemctl restart kiosk-dashboard` |
| `kiosk-http-server.service` | HTTP server porta 8505 para o HTML carousel | `sudo systemctl restart kiosk-http-server` |

---

## Troubleshooting

**Surf não aparece na tela:**
```bash
ssh homelab@192.168.15.2 "pgrep -a surf"
ssh homelab@192.168.15.2 "sudo systemctl status homelab-dashboard --no-pager -n 10"
```

**Verificar quantos dashboards estão no ciclo:**
```bash
ssh homelab@192.168.15.2 "sudo journalctl -t kiosk-rotation -n 10 --no-pager"
# "Dashboard X/7" → 7 = correto
```

**Reiniciar ciclo sem reiniciar serviço:**
```bash
ssh homelab@192.168.15.2 "sudo pkill xinit; sleep 3; pgrep -a surf"
# tty1-wrapper detecta saída do xinit e reinicia o loop automaticamente
```

**Rollback tty1-wrapper:**
```bash
ssh homelab@192.168.15.2 "ls /usr/local/bin/tty1-wrapper.bak-* | sort | tail -1"
ssh homelab@192.168.15.2 "sudo cp /usr/local/bin/tty1-wrapper.bak-TIMESTAMP /usr/local/bin/tty1-wrapper"
ssh homelab@192.168.15.2 "sudo systemctl restart homelab-dashboard"
```

---

## Commits desta sessão (branch fix/btc-panel114-calendar → PR #172)

| Hash | Descrição |
|------|-----------|
| `999aceae` | feat(grafana): habilitar embedding + carrossel kiosk com 3 perfis de trading |
| `50ecac5d` | fix(kiosk): habilitar rolagem dentro de cada página do carrossel |
| `34c5ff49` | feat(grafana): atualizar btc-trading-monitor para v2 com perfis completos |
| `2c065d53` | feat(kiosk): adicionar perfis aggressive e shadow ao carrossel tty1 |
| `e5b6978a` | fix(kiosk): substituir Page Down por mouse wheel scroll no surf |
