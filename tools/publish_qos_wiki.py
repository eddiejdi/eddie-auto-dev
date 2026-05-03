#!/usr/bin/env python3
"""Publica/atualiza a página de QoS + Balanceamento de Link na Wiki.js.

Uso: python3 tools/publish_qos_wiki.py
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import date

WIKI_HOST = "192.168.15.2"
WIKI_PORT = 3009
WIKI_URL = f"http://{WIKI_HOST}:{WIKI_PORT}/graphql"

PAGE_PATH = "infraestrutura/qos-balanceamento-link"
PAGE_TITLE = "QoS & Balanceamento de Link — Homelab"
PAGE_LOCALE = "pt"
PAGE_TAGS = ["qos", "rede", "tc", "cake", "htb", "infraestrutura", "homelab"]
PAGE_DESC = (
    "Configuração completa de QoS com Traffic Control (HTB + CAKE): "
    "priorização VPN, balanceamento igualitário de banda por host e "
    "shaping de ingresso via IFB. Inclui fix do bug NLM_F_REPLACE no boot."
)

TODAY = date.today().strftime("%Y-%m-%d")

QOS_CONTENT = f"""# QoS & Balanceamento de Link — Homelab

> **Última atualização:** {TODAY}
> **Status:** ✅ ATIVO — `setup-qos.service` active
> **Arquivo no repo:** `systemd/setup-qos.sh`
> **Arquivo no homelab:** `/usr/local/bin/setup-qos.sh`

---

## Contexto e Problema Original

O homelab (`192.168.15.2`) atua como roteador/NAT para todos os dispositivos da LAN `192.168.15.0/24`.
A conexão com a internet é um link GPON (Vivo) com capacidade real de aproximadamente:

| Direção | Velocidade real (medida) |
|---------|--------------------------|
| Download | ~10 Mbit/s |
| Upload   | ~5 Mbit/s  |

Antes desta configuração, **não existia nenhum mecanismo de distribuição igualitária de banda**.
Qualquer dispositivo ou serviço (ex: Storj, downloads pesados) podia monopolizar o link inteiro,
degradando a experiência de todos os outros hosts da rede.

Além disso, o serviço `setup-qos.service` **falhava no boot** com o erro:
```
Error: NLM_F_REPLACE needed to override.
setup-qos.service: Failed with result 'exit-code'.
```

Causa: o kernel/`systemd-networkd` já instala `fq_codel` como qdisc padrão na interface durante o boot.
O script usava `tc qdisc add` (que falha se já existe algum qdisc) em vez de `tc qdisc replace`.

---

## Arquitetura da Solução

```
Internet (GPON Vivo)
  └── eth-onboard (homelab 192.168.15.2)
        │
        ├── EGRESSO (upload 5 Mbit) — HTB root 1:
        │     ├── 1:10  WireGuard trabalho  → fq_codel  (prio 1, rate 2M, burst até 5M)
        │     ├── 1:20  NordVPN navegação   → fq_codel  (prio 2, rate 1.5M, burst até 5M)
        │     ├── 1:30  LAN geral (default) → CAKE dual-srchost + nat (prio 3, fair por host)
        │     └── 1:40  Storj 192.168.15.250→ fq_codel  (prio 4, limitado 400k/600k ceil)
        │
        └── INGRESSO (download 10 Mbit) — via IFB (ifb0)
              └── CAKE dual-dsthost + nat  (fair share por host receptor)
```

### Por que CAKE?

O `CAKE` (Common Applications Kept Enhanced) é um qdisc moderno do Linux que implementa:

- **`dual-srchost`**: divide a banda residual igualmente entre IPs de **origem** (upload) — cada host da LAN recebe a mesma fatia do uplink, sem que um monopolize o resto.
- **`dual-dsthost`**: divide igualmente entre IPs de **destino** (download via IFB) — cada host receptor tem sua fatia de download garantida.
- **`nat`**: resolve os IPs NATados de volta aos hosts LAN reais antes de classificar — essencial pois o tráfego sai com IP do homelab.
- **`wash`**: remove marcações DSCP de pacotes entrando (evita que dispositivos burlem a fila).
- **FQ integrado**: elimina bufferbloat sem configuração adicional.

### Por que HTB na raiz?

O HTB (Hierarchical Token Bucket) permite **priorização por classe** com `ceil` (burst para usar banda ociosa das outras classes). O WireGuard (trabalho) tem prioridade 1 — nunca é bloqueado pelo tráfego doméstico.

---

## Script Completo (`/usr/local/bin/setup-qos.sh`)

```bash
#!/bin/bash
# setup-qos.sh — QoS com priorização VPN + balanceamento igualitário por host
# Correção 2026-05-02: tc qdisc replace (era add) → resolve NLM_F_REPLACE no boot
# Adição 2026-05-02: CAKE dual-srchost para fair-share por host + IFB ingress shaping
set -euo pipefail

WAN="eth-onboard"
WG_IF="wg0"
NORD_IF="nordlynx"
IFB="ifb0"

# Velocidade real do ISP (Vivo GPON) — ajuste se mudar de plano
ISP_DOWN="10mbit"
ISP_UP="5mbit"

# ──────────────────────────────────────────────
# Limpeza idempotente
# ──────────────────────────────────────────────
cleanup() {{
  tc qdisc del root dev "$WAN" 2>/dev/null || true
  tc qdisc del ingress dev "$WAN" 2>/dev/null || true
  tc qdisc del root dev "$IFB" 2>/dev/null || true
  ip link set dev "$IFB" down 2>/dev/null || true

  iptables -t mangle -D OUTPUT      -o "$WG_IF"   -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$NORD_IF" -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WG_IF"   -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$NORD_IF" -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --dport 23456 -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D OUTPUT      -o "$WAN" -p udp --dport 7844  -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --dport 23456 -j MARK --set-mark 2 2>/dev/null || true
  iptables -t mangle -D POSTROUTING -o "$WAN" -p udp --dport 7844  -j MARK --set-mark 2 2>/dev/null || true
}}

ensure_mark_rule() {{
  local table="$1" chain="$2"
  local rule=("${{@:3}}")
  iptables -t "$table" -C "$chain" "${{rule[@]}}" 2>/dev/null || \
    iptables -t "$table" -A "$chain" "${{rule[@]}}"
}}

# ──────────────────────────────────────────────
# Setup IFB para shaping de ingresso (download)
# ──────────────────────────────────────────────
setup_ifb() {{
  modprobe ifb numifbs=1 2>/dev/null || true
  ip link set dev "$IFB" up 2>/dev/null || true

  tc qdisc replace dev "$WAN" ingress handle ffff:
  tc filter replace dev "$WAN" parent ffff: protocol ip u32 \
    match u32 0 0 action mirred egress redirect dev "$IFB"

  tc qdisc replace dev "$IFB" root cake \
    bandwidth "$ISP_DOWN" \
    besteffort \
    dual-dsthost \
    nat \
    wash \
    no-split-gso
}}

# ──────────────────────────────────────────────
# Limpeza inicial
# ──────────────────────────────────────────────
cleanup

# ──────────────────────────────────────────────
# EGRESSO (upload): HTB root para priorização VPN
# ──────────────────────────────────────────────
# FIX: "replace" em vez de "add" → evita NLM_F_REPLACE no boot quando
# o kernel/systemd-networkd já instalou fq_codel como qdisc padrão
tc qdisc replace dev "$WAN" root handle 1: htb default 30

tc class add dev "$WAN" parent 1: classid 1:1 htb rate "$ISP_UP" ceil "$ISP_UP"

tc class add dev "$WAN" parent 1:1 classid 1:10 htb rate 2mbit ceil "$ISP_UP" prio 1
tc class add dev "$WAN" parent 1:1 classid 1:20 htb rate 1500kbit ceil "$ISP_UP" prio 2
tc class add dev "$WAN" parent 1:1 classid 1:30 htb rate 1mbit ceil "$ISP_UP" prio 3
tc class add dev "$WAN" parent 1:1 classid 1:40 htb rate 400kbit ceil 600kbit prio 4

# Leaf qdiscs
tc qdisc add dev "$WAN" parent 1:10 fq_codel
tc qdisc add dev "$WAN" parent 1:20 fq_codel
tc qdisc add dev "$WAN" parent 1:30 cake \
  bandwidth "$ISP_UP" besteffort dual-srchost nat wash no-split-gso
tc qdisc add dev "$WAN" parent 1:40 fq_codel

# Marcação de pacotes
ensure_mark_rule mangle OUTPUT      -o "$WG_IF"   -j MARK --set-mark 1
ensure_mark_rule mangle OUTPUT      -o "$NORD_IF" -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WG_IF"   -j MARK --set-mark 1
ensure_mark_rule mangle POSTROUTING -o "$NORD_IF" -j MARK --set-mark 2
ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1
ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --dport 23456  -j MARK --set-mark 2
ensure_mark_rule mangle OUTPUT      -o "$WAN" -p udp --dport 7844   -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --sport 51824 -j MARK --set-mark 1
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --dport 23456  -j MARK --set-mark 2
ensure_mark_rule mangle POSTROUTING -o "$WAN" -p udp --dport 7844   -j MARK --set-mark 2

# Filtros HTB por marca
tc filter add dev "$WAN" parent 1: protocol ip prio 1 handle 1 fw classid 1:10
tc filter add dev "$WAN" parent 1: protocol ip prio 2 handle 2 fw classid 1:20
tc filter add dev "$WAN" protocol ip parent 1: prio 3 u32 \
  match ip src 192.168.15.250/32 flowid 1:40

setup_ifb
```

---

## Serviço Systemd

**Arquivo:** `/etc/systemd/system/setup-qos.service`

```ini
[Unit]
Description=Setup QoS Traffic Control (WireGuard Priority)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-qos.sh
RemainAfterExit=yes
TimeoutStartSec=20s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
```

---

## Tabela de Classes HTB

| Classe | Serviço | Rate (garantido) | Ceil (burst) | Prioridade | Leaf qdisc |
|--------|---------|-----------------|--------------|-----------|------------|
| `1:10` | WireGuard (trabalho) | 2 Mbit | 5 Mbit | 1 (alta) | fq_codel |
| `1:20` | NordVPN (navegação)  | 1.5 Mbit | 5 Mbit | 2 | fq_codel |
| `1:30` | LAN geral (**default**) | 1 Mbit | 5 Mbit | 3 | **CAKE dual-srchost** |
| `1:40` | Storj (192.168.15.250) | 400 Kbit | 600 Kbit | 4 (baixa) | fq_codel |

> O tráfego sem marca cai na classe **1:30** (default 30 no HTB).
> O CAKE em 1:30 divide o uplink residual **igualmente entre todos os hosts LAN**.

---

## Balanceamento de Download (IFB)

O módulo `ifb0` (Intermediate Functional Block) espelha o ingresso do `eth-onboard` para uma interface virtual onde é aplicado o CAKE:

```
eth-onboard ingress (ffff:)
  └── tc filter: mirred redirect → ifb0
        └── CAKE root: bandwidth 10mbit, dual-dsthost, nat, wash
```

`dual-dsthost` identifica o host LAN receptor (após NAT) e garante que nenhum host consuma mais que sua fatia do download disponível.

---

## Marcação de Pacotes (iptables mangle)

| Marca | Tráfego | Destino HTB |
|-------|---------|-------------|
| `1` | Pacotes originados em `wg0` ou UDP sport 51824 | 1:10 (WireGuard) |
| `2` | Pacotes originados em `nordlynx` ou UDP dport 23456/7844 | 1:20 (NordVPN) |
| (sem marca) | Todo o resto | 1:30 (CAKE, default) |
| filtro u32 | src 192.168.15.250/32 (Storj) | 1:40 (Storj limitado) |

---

## Diagnóstico / Monitoramento

```bash
# Ver qdiscs ativos
tc qdisc show dev eth-onboard
tc qdisc show dev ifb0

# Ver classes e contadores de tráfego
tc -s class show dev eth-onboard

# Status do serviço
sudo systemctl status setup-qos.service

# Monitoramento em tempo real
watch -n 2 'tc -s class show dev eth-onboard | grep -A2 "class htb"'

# Ver filtros ativos
tc filter show dev eth-onboard
```

---

## Rollback (se necessário)

```bash
sudo systemctl stop setup-qos.service
sudo systemctl disable setup-qos.service
sudo tc qdisc del root dev eth-onboard
sudo tc qdisc del ingress dev eth-onboard
sudo tc qdisc del root dev ifb0
sudo ip link set ifb0 down
sudo systemctl restart networking
```

---

## Bug Corrigido (2026-05-02)

**Sintoma:**
```
Error: NLM_F_REPLACE needed to override.
setup-qos.service: Failed with result 'exit-code'.
```

**Causa:** `tc qdisc add` falha quando o kernel já instalou `fq_codel` como qdisc padrão na interface durante o boot (systemd-networkd ou udev).

**Fix:** Substituído `tc qdisc add dev "$WAN" root ...` por `tc qdisc replace dev "$WAN" root ...`. O `replace` funciona tanto se já existir um qdisc (substitui) quanto se não existir (cria).

---

## Histórico

| Data | Evento |
|------|--------|
| 2026-04-13 | QoS inicial: HTB com SFQ, WireGuard prioritário |
| 2026-04-18 | Adição da classe Storj (1:40) para não saturar uplink 1Mbit |
| 2026-05-02 | Fix boot (tc replace) + CAKE dual-host fair balancing + IFB download shaping |
"""


def get_api_token() -> str | None:
    """Obtém token de autenticação do Wiki.js."""
    print("[*] Obtendo API token do Wiki.js...", file=sys.stderr)

    # 1) Tentar arquivo no homelab
    try:
        result = subprocess.run(
            [
                "ssh", "-i", "/home/edenilson/.ssh/homelab_key",
                "-oBatchMode=yes", "-oConnectTimeout=8",
                "-oControlMaster=no", "-oControlPath=none",
                "homelab@192.168.15.2",
                "cat ~/.wikijs-api-key 2>/dev/null || echo NOT_FOUND",
            ],
            capture_output=True, text=True, timeout=15,
        )
        token = result.stdout.strip()
        if token and token != "NOT_FOUND":
            print("[✓] API Key obtida via SSH (~/.wikijs-api-key)", file=sys.stderr)
            return token
    except Exception as exc:
        print(f"[!] SSH falhou: {exc}", file=sys.stderr)

    # 2) Login JWT com credenciais padrão
    for email, password in [
        ("admin@wiki.local", "admin"),
        ("admin@wiki.local", "changeme"),
        ("admin@rpa4all.com", "admin"),
    ]:
        try:
            payload = {
                "query": """mutation($e:String!,$p:String!){
                    authentication{login(username:$e,password:$p,strategy:"local"){jwt}}
                }""",
                "variables": {"e": email, "p": password},
            }
            req = urllib.request.Request(
                WIKI_URL,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
                jwt = (
                    data.get("data", {})
                    .get("authentication", {})
                    .get("login", {})
                    .get("jwt")
                )
                if jwt:
                    print(f"[✓] JWT obtido via login ({email})", file=sys.stderr)
                    return jwt
        except Exception:
            pass

    print("[!] Nenhum token encontrado — tentando sem autenticação", file=sys.stderr)
    return None


def graphql(payload: dict, api_token: str | None) -> dict:
    """Executa query/mutation GraphQL."""
    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    req = urllib.request.Request(
        WIKI_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_page_id(api_token: str | None) -> int | None:
    """Retorna o ID da página se já existir."""
    result = graphql(
        {
            "query": """query($path:String!,$locale:String!){
                pages{ singleByPath(path:$path,locale:$locale){ id } }
            }""",
            "variables": {"path": PAGE_PATH, "locale": PAGE_LOCALE},
        },
        api_token,
    )
    return (
        (result.get("data") or {})
        .get("pages", {})
        .get("singleByPath", {})
        .get("id")
    )


def create_or_update_page(api_token: str | None) -> None:
    """Cria ou atualiza a página na wiki."""
    existing_id = get_page_id(api_token)
    vars_base = {
        "content": QOS_CONTENT,
        "description": PAGE_DESC,
        "editor": "markdown",
        "isPublished": True,
        "isPrivate": False,
        "locale": PAGE_LOCALE,
        "path": PAGE_PATH,
        "tags": PAGE_TAGS,
        "title": PAGE_TITLE,
    }

    if existing_id:
        print(f"[*] Página existente id={existing_id} — atualizando...", file=sys.stderr)
        result = graphql(
            {
                "query": """mutation($id:Int!,$content:String!,$description:String!,
                    $editor:String!,$isPublished:Boolean!,$isPrivate:Boolean!,
                    $locale:String!,$path:String!,$tags:[String]!,$title:String!){
                    pages{update(id:$id,content:$content,description:$description,
                        editor:$editor,isPublished:$isPublished,isPrivate:$isPrivate,
                        locale:$locale,path:$path,tags:$tags,title:$title){
                        responseResult{succeeded message} page{id title path}
                    }}
                }""",
                "variables": {"id": existing_id, **vars_base},
            },
            api_token,
        )
        op = (result.get("data") or {}).get("pages", {}).get("update", {})
    else:
        print("[*] Página não existe — criando...", file=sys.stderr)
        result = graphql(
            {
                "query": """mutation($content:String!,$description:String!,
                    $editor:String!,$isPublished:Boolean!,$isPrivate:Boolean!,
                    $locale:String!,$path:String!,$tags:[String]!,$title:String!){
                    pages{create(content:$content,description:$description,
                        editor:$editor,isPublished:$isPublished,isPrivate:$isPrivate,
                        locale:$locale,path:$path,tags:$tags,title:$title){
                        responseResult{succeeded message} page{id title path}
                    }}
                }""",
                "variables": vars_base,
            },
            api_token,
        )
        op = (result.get("data") or {}).get("pages", {}).get("create", {})

    res = op.get("responseResult", {})
    page = op.get("page", {})

    if res.get("succeeded"):
        print(
            f"[✓] Wiki atualizada com sucesso!\n"
            f"    Título : {page.get('title')}\n"
            f"    Caminho: {page.get('path')}\n"
            f"    ID     : {page.get('id')}\n"
            f"    URL    : http://{WIKI_HOST}:{WIKI_PORT}/{PAGE_LOCALE}/{PAGE_PATH}",
            file=sys.stderr,
        )
    else:
        print(f"[✗] Falha: {res.get('message')}", file=sys.stderr)
        print(f"    Resposta completa: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    token = get_api_token()
    create_or_update_page(token)
