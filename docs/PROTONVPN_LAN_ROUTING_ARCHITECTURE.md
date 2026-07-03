# ProtonVPN — Arquitetura de Roteamento da LAN

**Data:** 2026-06-27  
**Status:** ✅ Implementado e documentado  
**Referência:** Incidente "celular sem internet" diagnosticado em 2026-06-27

---

## Princípio Fundamental

> **VPN é a regra. Bypass é a exceção explícita.**

Todo dispositivo que recebe IP via DHCP do homelab (`192.168.15.100–200`) roteia internet via ProtonVPN por padrão. O bypass direto via ISP é **opt-in explícito** — reservado para dispositivos IoT que quebram com VPN (Tuya, câmeras, streaming com geo-lock).

---

## Arquitetura de Roteamento

### Fluxo de um pacote saindo da LAN

```
Dispositivo LAN (ex: celular .102)
    │
    ▼ gateway = 192.168.15.2
eth-onboard (homelab)
    │
    ▼ ip rule lookup (em ordem de prioridade)
    │
    ├─ prio 150: from 192.168.15.{IoT list} → tabela isp-bypass
    │       │ → default via 192.168.15.1 dev eth-wan  ← ISP direto
    │       └─ nft ACCEPT (isp_bypass_devices set)
    │
    ├─ prio 32764: not fwmark 0xca6c → tabela 205
    │       │ → default dev protonvpn              ← ProtonVPN
    │       └─ nft ACCEPT (eth-onboard → protonvpn)
    │
    └─ [sem regra matching] → tabela main
            │ → default via 192.168.15.1 dev eth-wan
            └─ nft DROP (homelab-proxy chain: LAN→eth-wan sem bypass)
```

### Tabela de decisão por dispositivo

| Dispositivo | ip rule | Saída | Motivo |
|---|---|---|---|
| IoT (Tuya, câmera) | prio 150 → isp-bypass | eth-wan → ISP | Geo-lock / IP datacenter VPN detectado |
| Celular, notebook, TV não-IoT | prio 32764 → tabela 205 | protonvpn | Regra padrão |
| Homelab (192.168.15.2) | prio 32764 → tabela 205 | protonvpn | Mesma regra |
| Docker bridges (172.x) | tabela 205 (rotas locais) | direto | Rota local na tabela 205 |

---

## Componentes

### 1. nftables — `table ip homelab-proxy` (`homelab-proxy.nft`)

```nft
chain forward {
    # Aceita LAN→VPN (regra padrão)
    iifname "eth-onboard" oifname "protonvpn" ip saddr 192.168.15.0/24 accept

    # Aceita retorno do VPN→LAN
    iifname "protonvpn" oifname "eth-onboard" ct state established,related accept

    # Aceita bypass explícito (IoT whitelistado)
    iifname "eth-onboard" oifname "eth-wan" ip saddr @isp_bypass_devices accept

    # DROP qualquer LAN→eth-wan não whitelistada
    iifname "eth-onboard" oifname "eth-wan" ip saddr 192.168.15.0/24 drop
}
```

Esta regra DROP é o **guardião de segurança**: garante que dispositivos não-IoT nunca saiam direto pela internet sem VPN. Se as ip rules estiverem ausentes, o tráfego vira "network unreachable" para a LAN não-IoT.

### 2. Policy Routing — Regras críticas

```bash
# Regra principal: todo tráfego não-marcado como VPN → tabela 205
ip rule add not fwmark 0xca6c table 205 pref 32764

# Supressor: evita loop pelo default route da tabela main
ip rule add lookup main suppress_prefixlength 0 pref 32765
```

**Tabela 205** (ProtonVPN):
```
default dev protonvpn        # internet via VPN
192.168.15.0/24 dev eth-onboard  # LAN fica local
172.x.x.x dev br-*          # Docker bridges ficam locais
```

### 3. IoT Bypass — `iot-vpn-bypass.sh`

Adiciona regras source-based em prio 150 para dispositivos IoT:
```bash
ip rule add from 192.168.15.115 lookup isp-bypass prio 150  # Tuya plug
ip rule add from 192.168.15.110 lookup isp-bypass prio 150  # Chromecast
# ...
```

Identificação automática via `iot-dhcp-hook.sh` (chamado pelo dnsmasq). Classifica por OUI (Espressif, Tuya, Shelly, etc.) e hostname pattern.

---

## Problema: As Regras 32764/32765 Somem

### Causa

Quando o ProtonVPN reconecta (mudança de endpoint, restart por queda de link), o `wg-quick`/NM **derruba e recria** a interface `protonvpn`. Nesse processo, **todas as ip rules são removidas** — incluindo 32764 e 32765 que não são gerenciadas pelo NM.

Sem essas regras, o tráfego da LAN:
1. Cai no ip rule catch-all → tabela main → default via eth-wan
2. É aceito pelo kernel para encaminhamento
3. Bate no `homelab-proxy chain forward` → **DROP** (não está em isp_bypass_devices)

Resultado: todos os dispositivos LAN não-IoT ficam **sem internet** até as regras serem restauradas.

### Janela de impacto (antes dos fixes)

```
ProtonVPN reconecta
    │
    ├─ t+0s:   regras 32764/32765 removidas → LAN sem internet
    ├─ t+90s:  ExecStartPost do drop-in dispara watchdog (sleep 90)
    └─ t+0~5m: timer a cada 5min também pode pegar

Janela máxima de impacto: ~6 minutos
```

---

## Solução: Três Camadas de Proteção

### Camada 1 — NM Dispatcher (imediato) ✅ _novo_

**Arquivo:** `/etc/NetworkManager/dispatcher.d/51-protonvpn-policy-routing`  
**Fonte:** `deploy/vpn/51-protonvpn-policy-routing`

Executado pelo NetworkManager imediatamente quando a interface `protonvpn` sobe. Aplica as regras 32764/32765 sem delay.

```bash
# Lógica central do dispatcher
[[ "$IFACE" != "protonvpn" || "$ACTION" != "up" ]] && exit 0

ip rule add not fwmark 0xca6c table 205 pref 32764   # só se ausente
ip rule add lookup main suppress_prefixlength 0 pref 32765
ip route flush cache
```

### Camada 2 — Drop-in ExecStartPost (t+5s)

**Arquivo:** `/etc/systemd/system/wg-quick@protonvpn.service.d/restore-iprules.conf`

```ini
[Service]
ExecStartPost=/bin/bash -c 'sleep 5 && /usr/local/bin/protonvpn-routing-watchdog.sh --ensure || true &'
```

Backstop para o caso de o dispatcher NM não cobrir (ex: wg-quick sem NM). Reduzido de 90s para 5s.

### Camada 3 — Watchdog Timer (a cada 5min)

**Arquivo:** `protonvpn-routing-watchdog.service` + `.timer`

Health check completo a cada 5 minutos. Detecta e corrige qualquer desvio nas regras, rotas da tabela 205 e Docker bridges.

### Janela de impacto após fixes

```
ProtonVPN reconecta
    │
    ├─ t+0s:  regras removidas
    ├─ t~1s:  NM dispatcher executa → regras restauradas ✅
    └─ t+5s:  ExecStartPost watchdog confirma (backup)

Janela máxima de impacto: ~1 segundo
```

---

## Operação

### Diagnóstico: "dispositivo LAN sem internet"

```bash
# 1. Verificar se as regras críticas existem
ssh 192.168.15.2 "ip rule list | grep -E '32764|32765'"
# Esperado: ambas as linhas presentes

# 2. Verificar rota efetiva para o dispositivo
ssh 192.168.15.2 "ip route get 1.1.1.1 from <IP-DISPOSITIVO> iif eth-onboard"
# Esperado: "dev protonvpn table 205"
# Problema:  "Network is unreachable"

# 3. Verificar se o dispositivo está no bypass IoT (não deve estar para dispositivos normais)
ssh 192.168.15.2 "ip rule list | grep <IP-DISPOSITIVO>"
# Sem saída = dispositivo normal (vai via ProtonVPN)
# "lookup isp-bypass" = bypass IoT
```

### Fix imediato

```bash
ssh 192.168.15.2 "sudo /usr/local/bin/protonvpn-routing-watchdog.sh --fix"
```

### Adicionar dispositivo ao bypass IoT (EXCEÇÃO — use com cautela)

```bash
# Apenas para dispositivos que quebram com VPN (Tuya, câmeras, streaming geo-lock)
ssh 192.168.15.2 "sudo /usr/local/bin/iot-vpn-bypass.sh --add-device 192.168.15.XXX"

# Verificar lista atual de bypasses
ssh 192.168.15.2 "sudo /usr/local/bin/iot-vpn-bypass.sh --list"
```

### Verificar saúde geral do roteamento

```bash
ssh 192.168.15.2 "sudo /usr/local/bin/protonvpn-routing-watchdog.sh --health-check"
```

---

## DHCP e Atribuição de IP

O homelab (`192.168.15.2`) é o servidor DHCP da LAN via `dnsmasq`:

```
dhcp-range=192.168.15.100,192.168.15.200,2h
dhcp-option=3,192.168.15.2   # gateway = homelab
dhcp-option=6,192.168.15.2   # DNS = homelab
```

Dispositivos recebem `192.168.15.100–200` dinamicamente, a menos que tenham reserva estática (`dhcp-host=`). Dispositivos IoT críticos têm reservas fixas para garantir que as ip rules do bypass sejam estáveis.

**Config:** `/etc/dnsmasq.d/homelab-lan.conf`

---

## Incidente de Referência — 2026-06-27

**Sintoma:** Celular (192.168.15.102) conectado ao WiFi GVT-38AA mas sem internet.

**Timeline do diagnóstico:**
1. Ping do celular = OK (LAN funcionando)
2. DNS em 192.168.15.2 = OK (resolve connectivitycheck.gstatic.com)  
3. Scan de subnet = celular visível em .102
4. `ip route get 8.8.8.8 from 192.168.15.102` = **Network is unreachable**
5. nftables `homelab-proxy` = DROP para LAN→eth-wan sem bypass
6. ip rule list = **regras 32764/32765 ausentes**
7. Watchdog corrigiu automaticamente no ciclo seguinte (t+~8h desde o boot)

**Root cause:** ProtonVPN reconectou em algum momento do dia, derrubando as regras. O watchdog corrigiu mas levou até o próximo ciclo de 5min. O dispatcher NM foi adicionado para eliminar esta janela.

---

## Arquivos Relevantes

| Arquivo | Localização | Função |
|---|---|---|
| `51-protonvpn-policy-routing` | `deploy/vpn/` → `/etc/NetworkManager/dispatcher.d/` | Hook imediato ao subir protonvpn |
| `protonvpn-routing-watchdog.sh` | `deploy/vpn/` → `/usr/local/bin/` | Watchdog + health check + fix |
| `protonvpn-routing-watchdog.{service,timer}` | `deploy/vpn/` → `/etc/systemd/system/` | Timer 5min |
| `restore-iprules.conf` | `/etc/systemd/system/wg-quick@protonvpn.service.d/` | ExecStartPost t+5s |
| `homelab-proxy.nft` | `deploy/vpn/` → carregado na boot | DROP rule + masquerade |
| `iot-vpn-bypass.sh` | `deploy/vpn/` → `/usr/local/bin/` | Gerencia bypass IoT |
| `iot-dhcp-hook.sh` | `deploy/vpn/` → `/etc/iot-bypass/` | Auto-classifica IoT no DHCP |
| `homelab-lan.conf` | `/etc/dnsmasq.d/` | DHCP: range, gateway, DNS |
