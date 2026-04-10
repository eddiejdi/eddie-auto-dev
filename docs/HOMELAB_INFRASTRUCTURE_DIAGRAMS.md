# 🏗️ Diagramas de Infraestrutura — Homelab Shared

**Atualizado:** 2026-04-04

## 1. Visão Geral da Infraestrutura

```mermaid
graph TB
    subgraph "Internet"
        USER["👤 Usuário"]
        CF["☁️ Cloudflare Tunnel<br/>(rpa4all-tunnel)"]
        GDNS["Google DNS<br/>rpa4all.com"]
        TEL["Telegram API"]
        GH["GitHub"]
    end

    subgraph "Homelab — 192.168.15.2 (Ubuntu 24.04)"
        subgraph "Rede"
            NG["Nginx<br/>:80/:443"]
            WG["WireGuard VPN<br/>:51824/UDP<br/>10.66.66.0/24"]
            PH["Pi-hole DNS<br/>:53/:8053"]
            DP["DNSProxy DoH<br/>:8453"]
            CFD["cloudflared<br/>rpa4all.service"]
        end

        subgraph "Autenticação & SSO"
            AK["Authentik Server<br/>:9000/:9443"]
            AKW["Authentik Worker"]
            AKR["Redis :6379"]
            AKP["Auth Postgres :5432"]
        end

        subgraph "Serviços Web"
            GF["📊 Grafana<br/>:3002"]
            PR["Prometheus<br/>:9090"]
            AM["AlertManager<br/>:9093"]
            NC["☁️ Nextcloud<br/>:8880"]
            OW["🤖 OpenWebUI<br/>:3000"]
        end

        subgraph "Email @rpa4all.com"
            MS["📧 docker-mailserver<br/>Postfix+Dovecot+Rspamd<br/>:25/:465/:587/:993"]
            RC["Roundcube Webmail<br/>:9080"]
        end

        subgraph "LLM / IA"
            OL0["🧠 Ollama GPU0<br/>RTX 2060 SUPER 8GB<br/>:11434"]
            OL1["🧠 Ollama GPU1<br/>GTX 1050 2GB<br/>:11435"]
            LLM["LLM Optimizer<br/>:8512"]
        end

        subgraph "Trading (AutoCoinBot)"
            BTC["₿ BTC Agent<br/>:9092/:8511"]
            ETH["Ξ ETH Agent<br/>:9098/:8512"]
            XRP["XRP Agent<br/>:9094/:8513"]
            SOL["SOL Agent<br/>:9095/:8514"]
            DOGE["DOGE Agent<br/>:9096/:8515"]
            ADA["ADA Agent<br/>:9097/:8516"]
            EP["shared-postgres<br/>:5433<br/>btc_trading DB"]
        end

        subgraph "Shared Core"
            TB["🤖 Telegram Bot"]
            API["FastAPI<br/>:8503"]
            DIR["Diretor Agent"]
            COO["Coordinator Agent"]
            SA["Specialized Agents"]
            GHA["GitHub Agent<br/>:8080"]
        end
    end

    USER -->|HTTPS| CF
    CF --> CFD
    CFD --> NG
    CFD --> AK
    CFD --> GF
    CFD --> NC
    CFD --> OW
    CFD --> PH

    USER -->|WireGuard| WG
    USER -->|Telegram| TEL
    TEL --> TB

    AK -->|OAuth2| GF
    AK -->|OAuth2| NC
    AK -->|OAuth2| OW

    RC -->|IMAP/SMTP| MS
    GDNS -->|MX| MS

    TB --> OL0
    API --> OL0
    DIR --> OL0
    SA --> OL0
    LLM --> OL0
    LLM --> OL1

    BTC --> EP
    ETH --> EP
    XRP --> EP
    SOL --> EP
    DOGE --> EP
    ADA --> EP

    GF --> PR
    AM --> TEL
    PR --> BTC
    PR --> ETH

    GH --> GHA
```

## 2. Mapa de Portas

```mermaid
graph LR
    subgraph "Portas — Serviços Externos"
        direction TB
        E25["25 — SMTP"]
        E53["53 — DNS (Pi-hole)"]
        E80["80 — HTTP (Nginx)"]
        E143["143 — IMAP"]
        E443["443 — HTTPS (Nginx)"]
        E465["465 — SMTPS"]
        E587["587 — Submission"]
        E993["993 — IMAPS"]
        E3000["3000 — OpenWebUI"]
        E3002["3002 — Grafana"]
        E5433["5433 — PostgreSQL"]
        E8053["8053 — Pi-hole Web"]
        E8503["8503 — Shared API"]
        E8880["8880 — Nextcloud"]
        E9000["9000 — Authentik"]
        E9080["9080 — Roundcube"]
        E9090["9090 — Prometheus"]
        E11434["11434 — Ollama GPU0"]
        E11435["11435 — Ollama GPU1"]
        E51824["51824/UDP — WireGuard"]
    end
```

## 3. Fluxo de Autenticação OAuth2

```mermaid
sequenceDiagram
    participant U as Usuário
    participant G as Grafana/Nextcloud/OpenWebUI
    participant A as Authentik SSO
    participant DB as Auth Postgres

    U->>G: Acessa serviço
    G->>U: Redirect → auth.rpa4all.com
    U->>A: Login (username/password)
    A->>DB: Valida credenciais
    DB-->>A: OK / Erro
    alt Credenciais válidas
        A->>U: Redirect com authorization code
        U->>G: Callback com code
        G->>A: Troca code → access_token
        A-->>G: Token JWT + user info
        G->>U: Sessão autenticada ✅
    else Credenciais inválidas
        A->>U: "Invalid credentials" ❌
    end
```

## 4. Fluxo de Email

```mermaid
sequenceDiagram
    participant EXT as Email Externo
    participant DNS as Google DNS
    participant MX as mail.rpa4all.com
    participant MS as docker-mailserver
    participant RS as Rspamd
    participant DV as Dovecot
    participant RC as Roundcube
    participant U as Usuário

    Note over EXT,U: === Recepção de Email ===
    EXT->>DNS: MX lookup rpa4all.com
    DNS-->>EXT: mail.rpa4all.com (prio 10)
    EXT->>MX: SMTP :25
    MX->>MS: Postfix recebe
    MS->>RS: Anti-spam check
    RS-->>MS: Score
    MS->>DV: Entrega em Maildir
    U->>RC: Acessa webmail :9080
    RC->>DV: IMAP :143
    DV-->>RC: Emails
    RC-->>U: Exibe inbox

    Note over EXT,U: === Envio de Email ===
    U->>RC: Compõe email
    RC->>MS: SMTP :587 (autenticado)
    MS->>RS: DKIM sign
    RS-->>MS: Assinado
    MS->>EXT: SMTP :25 entrega
```

## 5. Rede e VPN

```mermaid
graph TB
    subgraph "Internet"
        CLOUD["☁️ Cloudflare"]
        VIVO["ISP: Vivo<br/>IP: 152.234.122.111"]
    end

    subgraph "LAN 192.168.15.0/24"
        ROUTER["Router"]
        subgraph "Homelab .2"
            ETH0["enp1s0<br/>192.168.15.2"]
            WG0["wg0<br/>10.66.66.1"]
        end
    end

    subgraph "VPN 10.66.66.0/24"
        PC["💻 PC (shared-client)<br/>10.66.66.2"]
        PHONE["📱 Android<br/>10.66.66.3"]
    end

    VIVO --> ROUTER
    ROUTER --> ETH0
    CLOUD -->|Tunnel| ETH0
    PC -->|WireGuard :51824| WG0
    PHONE -->|WireGuard :51824| WG0
    WG0 -->|MASQUERADE| ETH0
```

## 6. Camadas do Sistema Shared

```mermaid
graph TB
    subgraph "Camada 1 — Interface"
        TG["Telegram Bot"]
        ST["Streamlit :8502"]
        FA["FastAPI :8503"]
        VS["VS Code Extension"]
    end

    subgraph "Camada 2 — Orquestração"
        AM["Agent Manager"]
        AD["AutoDeveloper"]
        RM["RAG Manager"]
        DIR["Diretor"]
        COO["Coordinator"]
    end

    subgraph "Camada 3 — Agentes Especializados"
        PY["Python Agent"]
        JS["JS Agent"]
        TS["TS Agent"]
        GO["Go Agent"]
        RU["Rust Agent"]
        JA["Java Agent"]
        HL["Homelab Agent"]
    end

    subgraph "Camada 4 — Infraestrutura"
        OL["Ollama (Dual-GPU)"]
        CR["ChromaDB"]
        PG["PostgreSQL :5433"]
        DK["Docker"]
        GH["GitHub Actions"]
    end

    subgraph "Camada 5 — Serviços Homelab"
        AK["Authentik SSO"]
        CF["Cloudflare Tunnel"]
        WG["WireGuard VPN"]
        ML["Email Server"]
        NC["Nextcloud"]
        GR["Grafana + Prometheus"]
        PH["Pi-hole DNS"]
    end

    TG --> AM
    ST --> AM
    FA --> AM
    VS --> FA

    AM --> AD
    AM --> DIR
    AM --> COO
    AD --> RM

    AM --> PY
    AM --> JS
    AM --> TS
    AM --> GO
    AM --> HL

    PY --> OL
    PY --> CR
    PY --> PG
    PY --> DK
    HL --> PG
    HL --> DK

    AK -.-> GR
    AK -.-> NC
    CF -.-> AK
```

## 7. Trading Multi-Coin

```mermaid
graph LR
    subgraph "Crypto Agents (6 moedas)"
        BTC["₿ BTC<br/>:9092/:8511"]
        ETH["Ξ ETH<br/>:9098/:8512"]
        XRP["XRP<br/>:9094/:8513"]
        SOL["SOL<br/>:9095/:8514"]
        DOGE["DOGE<br/>:9096/:8515"]
        ADA["ADA<br/>:9097/:8516"]
    end

    subgraph "Infraestrutura Trading"
        PG["PostgreSQL :5433<br/>btc_trading / schema btc"]
        PR["Prometheus :9090"]
        GF["Grafana :3002"]
        AM["AlertManager :9093"]
        TG["Telegram Bot"]
    end

    BTC -->|PostgreSQL| PG
    ETH -->|PostgreSQL| PG
    XRP -->|PostgreSQL| PG
    SOL -->|PostgreSQL| PG
    DOGE -->|PostgreSQL| PG
    ADA -->|PostgreSQL| PG

    BTC -->|Prometheus metrics| PR
    ETH -->|Prometheus metrics| PR
    XRP -->|Prometheus metrics| PR

    PR --> GF
    AM --> TG
    PR --> AM
```

## 8. Serviços Systemd Ativos

```mermaid
graph TB
    subgraph "Serviços Críticos ⛔"
        SSH["sshd"]
        DOCKER["docker.service"]
        NGINX["nginx.service"]
        PIHOLE["pihole (container)"]
    end

    subgraph "Shared Core"
        TBOT["shared-telegram-bot"]
        SAPI["specialized-agents-api"]
        DIRET["diretor"]
        COORD["coordinator-agent"]
        EMON["shared-conversation-monitor"]
        ECAL["shared-calendar"]
        EEXP["shared-expurgo"]
    end

    subgraph "LLM & IA"
        OLL["ollama.service (GPU0)"]
        OLLM["ollama-frozen-monitor"]
        OMET["ollama-metrics-exporter"]
        LLMO["llm-optimizer"]
        GHAG["github-agent"]
    end

    subgraph "Trading"
        BTCA["btc-trading-agent"]
        BTCE["btc-engine-api"]
        ACBE["autocoinbot-exporter"]
        BANK["banking-metrics-exporter"]
        CAda["crypto-agent@ADA_USDT"]
        CDoge["crypto-agent@DOGE_USDT"]
        CEth["crypto-agent@ETH_USDT"]
        CSol["crypto-agent@SOL_USDT"]
        CXrp["crypto-agent@XRP_USDT"]
    end

    subgraph "Rede & Infra"
        CFRD["cloudflared-rpa4all"]
        AMGR["alertmanager"]
        AMTW["alertmanager-telegram-webhook"]
        DNSP["dnsproxy-doh"]
        GHA1["actions.runner (shared-auto-dev)"]
        GHA2["actions.runner (estou-aqui)"]
    end
```

## 9. Armazenamento

```mermaid
graph TB
    subgraph "Discos Físicos"
        SDA["sda1 — 298GB"]
        SDB["sdb1 — 298GB"]
        SDC["sdc3 — 455GB (87% usado)"]
    end

    subgraph "RAID (mergerfs)"
        RAID["/mnt/raid1<br/>585GB total, 502GB livre"]
    end

    subgraph "Dados no RAID"
        MAIL["/mnt/raid1/docker-mailserver/<br/>Email server + dados"]
        AUTH["/mnt/raid1/authentik/<br/>Authentik SSO"]
        BKUP["/mnt/raid1/backups/<br/>Snapshots"]
    end

    subgraph "Dados no SSD Principal"
        HOME["/home/homelab/<br/>Shared Auto-Dev"]
        DOCKV["/var/lib/docker/<br/>Container data"]
        OLLMOD["/usr/share/ollama/.ollama/models/<br/>LLM models"]
    end

    SDA --> RAID
    SDB --> RAID
    RAID --> MAIL
    RAID --> AUTH
    RAID --> BKUP
    SDC --> HOME
    SDC --> DOCKV
    SDC --> OLLMOD
```

## 10. Cloudflare Tunnel Routes

```mermaid
graph LR
    subgraph "Cloudflare DNS"
        DNS1["dns.rpa4all.com"]
        DNS2["www.rpa4all.com"]
        DNS3["openwebui.rpa4all.com"]
        DNS4["auth.rpa4all.com"]
        DNS5["nextcloud.rpa4all.com"]
        DNS6["grafana.rpa4all.com"]
        DNS7["*.rpa4all.com"]
    end

    subgraph "Homelab Services"
        S1[":8453 DNSProxy"]
        S2[":8090 Nginx Landing"]
        S3[":3000 OpenWebUI"]
        S4[":9000 Authentik"]
        S5[":8880 Nextcloud"]
        S6[":3002 Grafana"]
        S7[":8090 Nginx (fallback)"]
    end

    DNS1 --> S1
    DNS2 --> S2
    DNS3 --> S3
    DNS4 --> S4
    DNS5 --> S5
    DNS6 --> S6
    DNS7 --> S7
```

---

## 6. Topologia de Rede Física — Double-NAT (atualizado 2026-04-04)

```mermaid
graph TD
    subgraph ISP["🌐 ISP — Vivo/GVT"]
        PUB["IP Público<br/>191.202.237.52"]
    end

    subgraph CPE["Equipamentos de Borda"]
        ZTE["📡 ZTE GPON Modem<br/>192.168.14.1<br/>WAN: pública<br/>Vault: network/zte_gpon_modem"]
        TPL["🔀 TP-Link TL-WR740N<br/>WAN: 192.168.14.2<br/>LAN: 192.168.15.1<br/>Vault: network/tplink_router_001"]
    end

    subgraph LAN["LAN — 192.168.15.0/24"]
        HL["🖥️ Homelab Server<br/>192.168.15.2<br/>Ubuntu 24.04 LTS"]
        WS["💻 Workstation<br/>192.168.15.111<br/>LMDE"]
        NAS["💾 NAS/OMV<br/>192.168.15.4 / .24"]

        subgraph PLCS["Wi-Fi PLC Extenders"]
            PLC100["📶 TL-WPA4220 v4<br/>192.168.15.100<br/>Canal 11"]
            PLC103["📶 TL-WPA4220 v5<br/>192.168.15.103<br/>Canal 11"]
        end

        subgraph MACVLAN["Docker macvlan storj_macvlan"]
            STORJ["📦 storagenode<br/>192.168.15.250:28967<br/>Storj Node"]
        end
    end

    subgraph STORJNET["☁️ Storj Network — Satélites"]
        SAT1["Satélite 1wFTA..."]
        SAT2["Satélite 121RT..."]
        SAT3["Satélite 12Eay..."]
        SAT4["Satélite 12L9Z..."]
    end

    PUB -->|"Port-forward<br/>TCP+UDP 28967"| ZTE
    ZTE -->|"WAN 192.168.14.2<br/>Port-forward 28967"| TPL
    TPL -->|"LAN 192.168.15.x"| HL
    TPL --> WS
    TPL --> NAS
    TPL --> PLC100
    TPL --> PLC103

    HL -->|"macvlan"| STORJ

    STORJ -->|"UDP/TCP :28967<br/>via double-NAT"| SAT1
    STORJ -->|"UDP/TCP :28967"| SAT2
    STORJ -->|"UDP/TCP :28967"| SAT3
    STORJ -->|"UDP/TCP :28967"| SAT4

    style ZTE fill:#e8f4fd,stroke:#2980b9
    style TPL fill:#e8f4fd,stroke:#2980b9
    style STORJ fill:#d5f5e3,stroke:#27ae60
    style HL fill:#fef9e7,stroke:#f39c12
```

## 7. Fluxo de Port-Forward — Double-NAT Storj (2026-04-04)

```mermaid
sequenceDiagram
    participant SAT as ☁️ Satélite Storj
    participant INT as 🌐 Internet (191.202.237.52)
    participant ZTE as 📡 ZTE GPON<br/>(192.168.14.1)
    participant TPL as 🔀 TP-Link<br/>(192.168.14.2→15.1)
    participant HL as 🖥️ Homelab<br/>(192.168.15.2)
    participant STORJ as 📦 storagenode<br/>(192.168.15.250)

    Note over SAT,STORJ: Ping satellite → nó Storj

    SAT->>INT: TCP/UDP :28967 → 191.202.237.52
    INT->>ZTE: port-forward 28967 → 192.168.14.2
    ZTE->>TPL: encaminha :28967
    TPL->>STORJ: DNAT 28967 → 192.168.15.250:28967
    STORJ-->>SAT: resposta → node scores updated ✅

    Note over TPL,STORJ: Configuração TP-Link via GET<br/>/userRpm/VirtualServerRpm.htm?<br/>ExPort=28967&InPort=28967&<br/>Ip=192.168.15.250&Protocol=1&<br/>State=1&Changed=0&SelIndex=0&Page=1&Save=Save
```

## 8. Fluxo de Recovery — TP-Link Power-Cycle

```mermaid
flowchart TD
    START([🔴 Storj offline<br/>ping satellite failed]) --> CHECK1

    CHECK1{Port 28967<br/>acessível externamente?}
    CHECK1 -->|Não| CHECK2
    CHECK1 -->|Sim| CHECKLOGS

    CHECK2{ZTE port-forward<br/>28967 → 192.168.14.2?}
    CHECK2 -->|Não| FIXZTE
    CHECK2 -->|Sim| CHECK3

    FIXZTE[Configurar ZTE via Selenium<br/>ou urllib + frame navigation] --> CHECK3

    CHECK3{TP-Link httpd<br/>respondendo em :80?}
    CHECK3 -->|Sim ✅| APPLYTPL
    CHECK3 -->|Não — precisa power-cycle| POWERCYCLE

    POWERCYCLE["⚡ Power-cycle TP-Link<br/>(remover/religar cabo)"]
    POWERCYCLE --> WAIT["⏱️ Aguardar 60-120s<br/>polling TCP :80 a cada 3s"]
    WAIT --> APPLYTPL

    APPLYTPL["🐍 Executar script<br/>/tmp/tplink_pf_direct.py<br/>no homelab via SSH"]
    APPLYTPL --> VERIFY1{IP 192.168.15.250<br/>na lista do router?}

    VERIFY1 -->|Não| APPLYTPL
    VERIFY1 -->|Sim| CHECK4

    CHECK4{Storj backoff?<br/>>12 ping failures}
    CHECK4 -->|Sim| RESTART_STORJ["docker restart storagenode"]
    CHECK4 -->|Não| CHECKLOGS

    RESTART_STORJ --> CHECKLOGS

    CHECKLOGS["docker logs --since 90s storagenode<br/>grep 'node scores updated'"]
    CHECKLOGS --> DONE([✅ Storj online<br/>node scores updated<br/>todos satélites])

    style START fill:#ffcccc
    style DONE fill:#ccffcc
    style POWERCYCLE fill:#fff3cd
    style APPLYTPL fill:#cce5ff
```

