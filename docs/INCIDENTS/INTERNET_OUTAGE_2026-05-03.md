# Incidente — Falha de Navegação na Internet — 2026-05-03

> Diagnóstico e correção de falha intermitente de internet no homelab e na máquina local.

---

## Resumo Executivo

Em 2026-05-03 a navegação na internet ficou instável/inacessível. A causa raiz foi uma cadeia de 4 problemas independentes:

1. **WiFi Power Management ativo** — causava 40% de packet loss nas conexões sem fio
2. **Storm de processos `bw`** — saturava o HDD `sdd` a 90% de util, degradando o Squid e toda a navegação
3. **Pi-hole não subia após reboot** — Docker ainda `activating` quando pihole tentava iniciar
4. **`proxy.sh` incompleto** — terminal local nunca tinha `http_proxy` definido

Ao final da intervenção todos os 4 problemas foram corrigidos e self-heals foram implementados para prevenir reincidência.

---

## Topologia Relevante

```
Máquina local (esta)
  wlp2s0  — WiFi TANK (10.34.7.x, metric 600) — internet direta
  enp0s31f6 — RJ45 (192.168.15.x, metric 800)  — homelab

Homelab (192.168.15.2)
  Squid     :3128/:3129  — proxy de internet para browser/terminal
  Pi-hole   Docker        — DNS na LAN (upstream: NordVPN NordLynx Panama #3)
  NordLynx  WireGuard     — VPN de saída para DNS do Pi-hole
```

Todo o tráfego do browser passa pelo Squid via PAC file em `http://192.168.15.2/wpad.dat`.

---

## Causa Raiz 1 — WiFi Power Management

**Sintoma:** Pings para 8.8.8.8 via WiFi com 40% de packet loss.

**Causa:** NetworkManager mantinha `power save on` na interface `wlp2s0`.

**Correção aplicada:**
```bash
nmcli connection modify TANK 802-11-wireless.powersave 2
nmcli connection up TANK
```

**Correção permanente (pendente sudo pelo usuário):**
```bash
sudo tee /etc/NetworkManager/dispatcher.d/99-wifi-power-off > /dev/null << 'EOF'
#!/bin/bash
IFACE="$1"; ACTION="$2"
if [[ "$ACTION" == "up" && "$IFACE" == wlp* ]]; then
    /usr/sbin/iwconfig "$IFACE" power off 2>/dev/null || true
fi
EOF
sudo chmod +x /etc/NetworkManager/dispatcher.d/99-wifi-power-off
```

---

## Causa Raiz 2 — Storm de Processos `bw` (secrets_agent)

**Sintoma:** `sdd` (HDD 5400 RPM) a 90% de utilização; Squid lento; browser travando.

**Causa:** 4 bugs de concorrência no `secrets_agent.py` causavam 10–20+ processos `bw` simultâneos:

| Bug | Descrição |
|-----|-----------|
| **1** | Resultado negativo (`not found`) não era cacheado → cada request re-executava `bw` |
| **2** | `bw_get_secret_fields` não verificava cache antes de executar `bw list items` |
| **3** | Thundering herd: múltiplas threads viam cache vazio e todas spawnavm `bw` para a mesma chave |
| **4** | Sem limite global de concorrência → chaves diferentes criavam muitos `bw` em paralelo |

**Arquivo corrigido:** `/home/homelab/agents_workspace/prod/tools/secrets_agent/secrets_agent.py`
(backup em `secrets_agent.py.bak-20260503*`)

Veja detalhes completos em [secrets_agent_concurrency_fixes.md](../secrets_agent_concurrency_fixes.md).

---

## Causa Raiz 3 — Pi-hole Não Subia Após Reboot

**Sintoma:** YouTube abria o site mas vídeos não executavam; DNS para `*.googlevideo.com` falhava.

**Causa:** `pihole.service` iniciava enquanto o Docker ainda estava em estado `activating`. O container falhava silenciosamente.

**Correção:** Drop-in `wait-docker.conf` no homelab:
```
/etc/systemd/system/pihole.service.d/wait-docker.conf
```
```ini
[Service]
ExecStartPre=/bin/bash -c 'for i in $(seq 1 30); do docker info >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1'
Restart=on-failure
RestartSec=15
StartLimitBurst=5
StartLimitIntervalSec=120
```

**Problema secundário:** `pihole-upstream-vpn-routes.service` falhava porque `nordlynx` não estava pronto.

**Correção:** Drop-in `soft-dep.conf`:
```
/etc/systemd/system/pihole-upstream-vpn-routes.service.d/soft-dep.conf
```
```ini
[Unit]
Requires=
Wants=sys-subsystem-net-devices-nordlynx.device nordvpnd.service
```

---

## Causa Raiz 4 — `proxy.sh` Incompleto

**Sintoma:** Terminal local sem acesso à internet mesmo com Squid funcional.

**Causa:** `/home/edenilson/.config/homelab/proxy.sh` definia `NO_PROXY` mas nunca exportava `http_proxy` / `https_proxy`.

**Correção aplicada:**
```bash
# Adicionado após o if:
export HTTP_PROXY="http://${_PROXY_HOST}:${_PROXY_PORT}"
export HTTPS_PROXY="http://${_PROXY_HOST}:${_PROXY_PORT}"
export http_proxy="${HTTP_PROXY}"
export https_proxy="${HTTPS_PROXY}"
```

---

## Self-Heals Implementados

Quatro mecanismos adicionados ao `critical-services-watchdog.sh` no homelab:

| Mecanismo | Gatilho | Ação |
|-----------|---------|------|
| Pi-hole auto-heal | `docker inspect pihole` não running | `systemctl start pihole.service` |
| bw overflow auto-heal | `pgrep bw` > 3 processos | `killall -9 bw` + `systemctl restart secrets_agent` |
| Notificação Telegram | Qualquer heal executado | Mensagem via bot do homelab |
| Semáforo em `run_command` | Sempre | Limita a 2 processos `bw` simultâneos no máximo |

Também adicionado drop-in para silenciar logs do Ollama no syslog:
```
/etc/systemd/system/ollama.service.d/zz-quiet-syslog.conf
```

---

## Estado Final

| Componente | Status |
|------------|--------|
| WiFi packet loss | Resolvido (power management off) |
| sdd utilização | ~20% (era 90%) |
| secrets_agent bw storm | Resolvido (4 bugs + semáforo) |
| Pi-hole no boot | Resolvido (wait-docker drop-in) |
| proxy.sh terminal | Resolvido |
| YouTube vídeos | Funcional |
| VPN NordLynx | Funcional |

---

## Lições Aprendidas

1. HDD lento (`sdd`) é o gargalo central — qualquer storm de I/O derruba toda a internet (tráfego passa pelo Squid)
2. Serviços que dependem de Docker precisam de `ExecStartPre` com polling — `After=docker.service` não garante containers prontos
3. `threading.Event` por chave é mais eficiente que semáforo global para dedup de fetches
4. `proxy.sh` deve ser testado com `curl -v` para confirmar que `http_proxy` está ativo
