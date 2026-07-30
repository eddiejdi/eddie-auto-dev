# Incidente — LAN sem internet por perda das rules 32764/32765 — 2026-07-29

> Queda espontânea de internet na LAN (notebook RJ45/GVT e demais clientes não-IoT).
> Causa: policy routing ProtonVPN (`ip rule` 32764/32765) sumiu sozinha; selfheal
> restaurou em ~5 min. Mitigações: timer 60s + ensure leve em heals colaterais.

**Status:** mitigado em produção (homelab) + versionado no repo  
**Host:** `192.168.15.2` (homelab)  
**Backup deploy:** `/root/backup-vpn-rules-20260729-222921`

---

## Resumo executivo

Por volta de **22:09–22:14 -03**, a internet da LAN “morreu sem ninguém tocar”.

1. As rules de policy routing **`32764`** (`not fwmark 0xca6c → table 205`) e **`32765`**
   (`lookup main suppress_prefixlength 0`) **desapareceram**.
2. Clientes LAN não-IoT caíram no path default `eth-wan` e no **DROP** do `homelab-proxy`
   (só IoT em `isp-bypass` passa).
3. O `protonvpn-routing-watchdog` detectou o desvio às **22:14:22** e restaurou às **22:14:27**.
4. Em paralelo, o notebook (ainda no SSID **TANK**) teve flap de Wi‑Fi — sintoma local
   amplificado, não a causa-raiz do homelab.

---

## Timeline (homelab)

| Hora (local) | Evento |
|--------------|--------|
| 22:09:21 | Watchdog: rules OK, saída via ProtonVPN (`79.127.164.75`) |
| 22:09–22:14 | Janela: rules 32764/32765 ausentes |
| 22:12:25 | `iot-vpn-bypass --heal` recriou **todos** os `ip rule` IoT (“Bypass IoT restaurado”) |
| 22:12–22:14 | `cloudflared` unhealthy; tunnel-heal em loop em `cloudflared-vpn-routes.sh` |
| 22:14:01 | `protonvpn-unit-selfheal`: unit `wg-quick@protonvpn` **inactive**, handshake **136s** |
| 22:14:22 | Watchdog: `32764 ausente`, tráfego **não** sai por `protonvpn`, IP público **ISP** `189.27.196.49` |
| 22:14:23–27 | Autocorreção: rules restauradas, IP de volta a `79.127.164.75` |
| 22:29 | Deploy de mitigações (timer 60s + ensure hooks); backup em `/root/backup-vpn-rules-20260729-222921` |

Único “Desvio crítico” do watchdog nos **7 dias** anteriores a este incidente.

---

## Causa raiz

**Policy routing da LAN→ProtonVPN é efêmera e não é reaplicada em todos os caminhos de heal.**

Arquitetura canônica (ver `docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`):

- VPN é a **regra** (table 205 / rules 32764–32765).
- Bypass ISP é **exceção** (prio 150, IoT).
- Sem 32764, o tráfego LAN não-IoT tenta `eth-wan` e é **dropado** pelo nft `homelab-proxy`.

Gatilho provável da limpeza de rules (não 100% atribuído a um único PID):

- reconexão / rehandshake do stack ProtonVPN (iface viva, mas `wg-quick@protonvpn` inactive);
- em paralelo, storm de heals (`iot-vpn-bypass`, `cloudflared-vpn-routes`) rodando **sem** reaplicar 32764/32765.

Documentado previamente em:

- `docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`
- `deploy/vpn/README-protonvpn-watchdog.md`
- memória `feedback_protonvpn_lan_routing_gap`

---

## Impacto

| Quem | Efeito |
|------|--------|
| Notebook / celulares / LAN não-IoT | Sem internet (ou “network unreachable” / DROP silencioso) |
| IoT em isp-bypass | Em geral preservado (prio 150) |
| Homelab outbound via eth-wan | Continuava OK no ISP (`189.x`) durante a janela |
| Cloudflare Tunnel | Flaps / DOWN transitório no mesmo intervalo |

---

## Mitigações deployadas (2026-07-29)

### Código / units (repo → host)

| Item | Mudança |
|------|---------|
| `protonvpn-routing-watchdog.timer` | `OnUnitActiveSec` **5min → 60s** |
| `ensure-protonvpn-policy-rules.sh` | **Novo** — reaplica só 32764/32765 (leve) |
| `iot-vpn-bypass --heal/--restore` | Chama ensure no final (patch no host) |
| `cloudflared-vpn-routes.sh` | Chama ensure no final |
| `wan-selfheal.sh` | Chama ensure no final (patch no host) |
| `wg-quick@protonvpn` `restore-iprules.conf` | ensure imediato + CF routes + watchdog em **t+5s** (era sleep 90) |

### Validação pós-deploy

- `ip rule`: 32764/32765 presentes
- `ip route get 1.1.1.1 from 192.168.15.137 iif eth-onboard` → `dev protonvpn table 205`
- `protonvpn-routing-watchdog.sh --health-check` → OK
- Notebook: Google HTTP 200, IP público `79.127.164.75`

### Rollback

```bash
ssh homelab
sudo cp -a /root/backup-vpn-rules-20260729-222921/. /staging-review/
# restaurar paths originais a partir do backup, depois:
sudo systemctl daemon-reload
sudo systemctl restart protonvpn-routing-watchdog.timer
```

---

## Preferência de internet no notebook (hook de agente)

Além do incidente de infra, ficou registrado o contrato operacional do usuário:

1. **RJ45** (`enp0s31f6`) preferencial  
2. **Wi‑Fi GVT-38AA** preferencial  
3. **TANK** só fallback  

Hook: `tools/copilot_hooks/internet_preference_context.py` (`UserPromptSubmit` em Claude/Grok).  
Política: `AGENTS.md` item 8.

---

## Lições aprendidas

1. “Internet caiu sem tocar” na LAN deste homelab → **primeiro** checar `ip rule | grep -E '32764|32765'`.
2. Watchdog a cada 5 min deixa janela longa demais quando rules somem.
3. Heals de IoT/CF/WAN **devem** reaplicar as rules da LAN VPN, senão “curam o satélite e deixam o planeta offline”.
4. `wg-quick@protonvpn` inactive + iface `protonvpn` viva = stack mista; dispatcher NM pode não disparar.

---

## Fix imediato (operacional)

```bash
ssh 192.168.15.2 "sudo /usr/local/bin/protonvpn-routing-watchdog.sh --fix"
# ou só rules:
ssh 192.168.15.2 "sudo /usr/local/bin/ensure-protonvpn-policy-rules.sh"
ssh 192.168.15.2 "sudo /usr/local/bin/protonvpn-routing-watchdog.sh --health-check"
```

---

## Arquivos relacionados

- `deploy/vpn/ensure-protonvpn-policy-rules.sh`
- `deploy/vpn/protonvpn-routing-watchdog.timer`
- `deploy/vpn/protonvpn-routing-watchdog.sh`
- `deploy/vpn/cloudflared-vpn-routes.sh`
- `deploy/vpn/restore-iprules.conf`
- `deploy/vpn/51-protonvpn-policy-routing`
- `docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`
- `tools/copilot_hooks/internet_preference_context.py`
