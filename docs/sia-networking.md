# Rede do nó Sia (`hostd`) — cadeia macvlan/host-shim/proxy

Espelha exatamente a cadeia já usada pelo Storj (`docs/storj-selfheal-grafana.md`), com IPs/portas
próprios. Container `hostd` fica isolado numa rede macvlan própria (`sia_macvlan`), inatingível
diretamente pelo host — por isso a cadeia de shim + proxies abaixo.

```
sia-macvlan-network.service   — cria a rede macvlan /32 (IP .252)
        │ Before=
        ▼
sia-host-shim.service         — iface sia-host0 no host @ .253; ip route + ip rule
                                 priority 96/97 para desviar da tabela 205 (policy routing ProtonVPN)
        │ watched by
        ▼
sia-macvlan-watchdog.service/.timer — a cada 2min, corrige eth0 ausente no container

sia-port-forward.service      — iptables DNAT/MASQUERADE: WAN eth-wan → .252:9981/tcp (consensus)
                                 e .252:9984/tcp+udp (RHP4)
sia-api-proxy.socket + .service — proxy localhost:9980 → 192.168.15.252:9980 (API/UI do hostd),
                                 via /lib/systemd/systemd-socket-proxyd (mesmo binário usado pelo
                                 storj-api-proxy.service, confirmado no host homelab)
```

## Diferença deliberada em relação ao Storj

O equivalente Storj destas duas últimas units (`storj-port-forward.service`,
`storj-api-proxy.socket`/`.service`) só existe no host (`/etc/systemd/system/`), fora deste repo.
Para o Sia, essas units já nascem **versionadas** — corrige uma lacuna conhecida (units host-only
não são recuperáveis se o host for reconstruído do zero).

## Portas

| Porta | Protocolo | Uso |
|---|---|---|
| 9980 | tcp | API/UI do `hostd` — **NUNCA expor à WAN**, só via `sia-api-proxy.socket` (localhost) |
| 9981 | tcp | Consensus/gossip da rede Sia |
| 9984 | tcp+udp | RHP4 — protocolo atual renter↔host (substituiu RHP2/RHP3) |
