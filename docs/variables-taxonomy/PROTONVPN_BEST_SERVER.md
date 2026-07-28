# ProtonVPN Best Server — Variáveis

Serviço: `protonvpn-best-server.service` (+ `.timer`, **de hora em hora**) —
script `tools/homelab/protonvpn_best_server.py`, instalado em
`/usr/local/bin/protonvpn_best_server.py` no homelab (192.168.15.2).

Mede RTT/perda dos servidores ProtonVPN candidatos e troca **apenas o bloco
`[Peer]`** do túnel para o mais rápido, aplicando com `wg syncconf`.

**Por que syncconf e não `wg-quick down/up`:** a conf
`/etc/wireguard/protonvpn.conf` carrega ~40 regras `PostUp` (tabela 205,
`fwmark 0xca6c`, rotas da LAN, bridges Docker 172.x, exceções de edge Cloudflare
por UID `_rpa4all`, macvlan Storj, kill-switch). `syncconf` atualiza o peer no
kernel sem disparar `PostDown`/`PostUp` — nenhuma regra de roteamento é tocada.
Como o homelab é o gateway da LAN, derrubar o túnel derrubaria a casa.

**Anti-alternância:** a troca só ocorre se o candidato for `PVPN_MIN_GAIN_PCT`
melhor **e** o dwell mínimo (`PVPN_MIN_DWELL_SEC`) tiver vencido. O timer horário
é o piso da cadência; o dwell é o teto.

**Rollback automático:** se o peer novo não fechar handshake em
`PVPN_HANDSHAKE_TIMEOUT_SEC`, a conf anterior é restaurada e reaplicada.

Métricas em `/var/lib/prometheus/node-exporter/protonvpn_best_server.prom`
(o collector ativo é esse — `/var/lib/node_exporter/textfile_collector/` **não**
é lido pelo node-exporter deste host).

| Variável | Default | Propósito |
|---|---|---|
| `PVPN_IFACE` | `protonvpn` | Nome da interface WireGuard do túnel Proton. |
| `PVPN_CONF` | `/etc/wireguard/protonvpn.conf` | Config wg-quick cujo bloco `[Peer]` é reescrito. O `[Interface]` (com os PostUp) nunca é tocado. |
| `PVPN_CANDIDATES` | `/etc/protonvpn-best-server.json` | Lista de servidores candidatos (`name`, `country`, `public_key`, `endpoint`), gerada a partir das configs WireGuard baixadas em account.protonvpn.com. |
| `PVPN_STATE` | `/var/lib/protonvpn-best-server/state.json` | Estado persistente — guarda `last_switch_ts` para o dwell mínimo sobreviver a reboot. |
| `PVPN_METRICS` | `/var/lib/prometheus/node-exporter/protonvpn_best_server.prom` | Saída textfile collector das métricas Prometheus. |
| `PVPN_MIN_GAIN_PCT` | `20` | Ganho mínimo (%) sobre o servidor atual para justificar a troca. Abaixo disso dois servidores empatados dentro do ruído ficariam se revezando. |
| `PVPN_MIN_DWELL_SEC` | `3600` | Tempo mínimo (s) no mesmo servidor antes de considerar outra troca — 1h, conforme cadência pedida. |
| `PVPN_PING_COUNT` | `10` | Pacotes ICMP por candidato na medição. Menos que isso torna a média sensível a um outlier. |
| `PVPN_PING_FWMARK` | `51820` | Marca (`ping -m`, decimal de `0xca6c`) que faz a medição escapar da tabela 205 e sair direto pela `eth-wan`. **Sem ela a medição sai pelo túnel atual** e todos os candidatos medem ~RTT do servidor atual, tornando a escolha aleatória — medido no homelab: 1.1.1.1 a 206ms com o túnel contra 7ms sem. Exige root. |
| `PVPN_LOSS_PENALTY_MS` | `8` | Penalidade em ms por 1% de perda no score. Perda trava vídeo, latência só atrasa — por isso perda pesa mais que RTT puro. |
| `PVPN_HANDSHAKE_TIMEOUT_SEC` | `25` | Prazo para o peer novo fechar handshake antes do rollback automático. |

## Formato do arquivo de candidatos

```json
{
  "servers": [
    {
      "name": "AR#12",
      "country": "AR",
      "public_key": "<PublicKey do [Peer] da config baixada>",
      "endpoint": "<ip>:51820"
    }
  ]
}
```

Os valores saem das configs WireGuard geradas em account.protonvpn.com →
*WireGuard configuration* (uma por servidor). Só `PublicKey` e `Endpoint` do
bloco `[Peer]` são necessários — a `PrivateKey` do `[Interface]` continua sendo
a que já está na conf do túnel.

> **Validar antes de confiar:** a `PrivateKey` atual precisa estar registrada
> para os servidores novos. Se o certificado tiver sido gerado por servidor, o
> handshake falha e o rollback automático devolve o peer anterior — rode
> `--apply` uma vez à mão e confira o log antes de habilitar o timer.
