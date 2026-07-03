# Incidente — Grafana Monitoring Outage 2026-06-29

**Data:** 2026-06-29  
**Duração:** ~1h15min (08:28–09:43 BRT)  
**Severidade:** Alta (todos os painéis Prometheus em No Data)  
**Dashboards afetados:** Ollama GPU Cluster, Storj Storage Node, BTC Trading Monitor

---

## Resumo executivo

Três problemas independentes detectados e corrigidos em sequência:

| # | Problema | Causa | Fix |
|---|----------|-------|-----|
| 1 | Todos os painéis Prometheus em No Data | Container `prometheus` parado (exit 255) | `docker start prometheus` |
| 2 | Panel QUIC = 0 e Ganhos Mês Atual = No Data no Storj | `storj-api-proxy.socket` dead | `systemctl start storj-api-proxy.socket` + restart exporter |
| 3 | Todos os painéis em No Data com filtro `servidor=orangepi` | OrangePi (192.168.15.3) ausente do `prometheus.yml` | 3 scrape jobs adicionados |

---

## Problema 1 — Prometheus parado

### Sintoma
- Grafana datasource Prometheus: `ERROR — connection refused http://172.17.0.1:9090`
- Todos os 68 painéis Prometheus do BTC Trading Monitor, 25 do Storj e 14 do Ollama sem dados

### Diagnóstico
```bash
docker ps -a --filter name=prometheus
# → prometheus Exited (255) About an hour ago

docker inspect prometheus --format '{{.State.FinishedAt}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
# → 2026-06-29T11:28:50Z exit=255 oom=false

journalctl -u docker --since "2h" | grep prometheus
# → "ShouldRestart failed ... hasBeenManuallyStopped=true"
```

**Causa raiz:** container parado manualmente (provavelmente `docker stop` durante manutenção). A política `restart: unless-stopped` não relança quando há parada explícita.

### Correção
```bash
docker start prometheus
sleep 5 && curl http://localhost:9090/-/healthy
# → Prometheus Server is Healthy.
```

---

## Problema 2 — storj-api-proxy.socket dead

### Sintoma (pós-fix do Prometheus)
- `storj_node_quic_ok = 0` (panel 2 "QUIC" mostrava DEGRADED)
- `storj_payout_current_gross_total_cents` → No Data (panel 5 "Ganhos Mês Atual")
- `storj-exporter` expondo apenas `storj_exporter_up 1`

### Diagnóstico
```bash
journalctl -u storj-exporter.service --since "1h" | tail -5
# → WARNING Erro ao acessar Storj API sno/: [Errno 111] Connection refused

systemctl status storj-api-proxy.socket
# → Active: inactive (dead)

# Storj node API diretamente via macvlan:
curl http://192.168.15.250:14002/api/sno/ | jq .quicStatus
# → "OK"
```

**Causa raiz:** o `storj-exporter.py` usa `http://localhost:14002/api` (via proxy systemd socket). O `storj-api-proxy.socket` faz `localhost:14002 → 192.168.15.250:14002`. Com o socket inativo, o exporter recebia connection refused em todas as chamadas, retornando apenas a métrica de sentinela `storj_exporter_up 1`.

O mesmo socket é usado pelo `storj-selfheal-exporter.py` para ler `quicStatus` da API. Sem acesso, `state.quic_ok` ficava `False` (default) → `storj_node_quic_ok = 0`.

### Correção
```bash
sudo systemctl start storj-api-proxy.socket
sudo systemctl restart storj-exporter.service
sleep 6 && curl -s http://172.17.0.1:9651/metrics | grep 'quic_ok\|payout'
```

### Bug adicional — métrica `storj_payout_current_gross_total_cents` removida

Após restaurar o socket, o exporter voltou a coletar dados mas `storj_payout_current_gross_total_cents` (panel 5) continuou em No Data: a métrica havia sido removida em uma refatoração anterior do exporter.

**Arquivo:** `tools/storj_exporter.py`  
**Problema:** `_metric("storj_payout_current_month_cents", egress_pay + disk_pay)` não incluía `egressRepairAuditPayout` e não publicava o nome `storj_payout_current_gross_total_cents` que o dashboard espera.

**Correção aplicada:**
```python
repair_audit_pay = current.get("egressRepairAuditPayout", 0)
gross_total = egress_pay + disk_pay + repair_audit_pay

self._metric(lines, "storj_payout_current_gross_total_cents",
             gross_total,
             "Ganhos brutos totais mês atual (egress+storage+repair, centavos USD)")
self._metric(lines, "storj_payout_current_month_cents",
             gross_total, ...)
self._metric(lines, "storj_payout_current_repair_audit_cents",
             repair_audit_pay, ...)
```

Também adicionado `storj_payout_previous_repair_audit_cents` para consistência histórica.

---

## Problema 3 — OrangePi ausente do prometheus.yml

### Sintoma
- Dashboard BTC com `var-servidor=orangepi`: 100% dos painéis No Data
- `servidor=orangepi` aparecia na lista de opções do template variable pois havia séries históricas no TSDB, mas nenhuma recente

### Diagnóstico
```bash
# Verificar label values
curl 'http://localhost:9090/api/v1/label/servidor/values'
# → ["homelab", "orangepi"]   ← 'orangepi' existe mas só em séries antigas

# Testar porta no OrangePi
for p in 9094 9095 9099; do
  timeout 1 bash -c ">/dev/tcp/192.168.15.3/$p" && echo "port $p OPEN"
done
# → port 9094 OPEN, port 9095 OPEN, port 9099 OPEN

# Verificar que métricas estão sendo publicadas
curl http://192.168.15.3:9094/metrics | grep btc_trading_agent_running
# → btc_trading_agent_running{coin="BTC-USDT",profile="conservative"} 1
```

**Causa raiz:** o `prometheus.yml` só tinha jobs para `172.17.0.1` (homelab) com `servidor: homelab`. O OrangePi (`192.168.15.3`) tinha os três agentes BTC rodando com exporters ativos, mas nenhum scrape job apontava para ele.

### Correção — `monitoring/prometheus.yml`

Adicionados 3 scrape jobs após o bloco `crypto-exporter-btc_usdt_shadow`:

```yaml
- job_name: 'crypto-exporter-orangepi-conservative'
  scrape_interval: 30s
  static_configs:
    - targets: ['192.168.15.3:9094']
      labels:
        coin: 'BTC-USDT'
        instance: 'btc_usdt_conservative'
        profile: 'conservative'
        servidor: 'orangepi'

- job_name: 'crypto-exporter-orangepi-aggressive'
  scrape_interval: 30s
  static_configs:
    - targets: ['192.168.15.3:9095']
      labels:
        coin: 'BTC-USDT'
        instance: 'btc_usdt_aggressive'
        profile: 'aggressive'
        servidor: 'orangepi'

- job_name: 'crypto-exporter-orangepi-shadow'
  scrape_interval: 30s
  static_configs:
    - targets: ['192.168.15.3:9099']
      labels:
        coin: 'BTC-USDT'
        instance: 'btc_usdt_shadow'
        profile: 'shadow'
        servidor: 'orangepi'
```

Reload sem restart:
```bash
docker kill --signal=HUP prometheus
# valida automaticamente — rejeita config inválido sem interromper
```

---

## Estado final

| Componente | Status |
|------------|--------|
| Prometheus | ✅ running, 22 targets ativos |
| storj-api-proxy.socket | ✅ active |
| storj-exporter | ✅ 40+ métricas publicando |
| storj_node_quic_ok | ✅ 1 (OK) |
| storj_payout_current_gross_total_cents | ✅ 0.6459 USD |
| orangepi targets | ✅ 3/3 up (conservative, aggressive, shadow) |

---

## Checklist de diagnóstico (para futuras ocorrências)

### Todos os painéis Prometheus em No Data
```bash
docker ps -a --filter name=prometheus
curl http://localhost:9090/-/healthy
docker start prometheus   # se exited
```

### Storj: QUIC=0 ou payout sem dados
```bash
systemctl is-active storj-api-proxy.socket
# se inativo:
sudo systemctl start storj-api-proxy.socket
sudo systemctl restart storj-exporter.service
curl http://172.17.0.1:9651/metrics | grep -c '^storj_'
# deve retornar ~40
```

### Dashboard mostra servidor=X com No Data
```bash
grep -A8 "servidor.*$X" /home/homelab/monitoring/prometheus.yml
# se não encontrar: adicionar scrape job para o IP do servidor X
curl http://localhost:9090/api/v1/targets | python3 -c "
import sys,json; [print(t['labels'].get('servidor'), t['health'], t['scrapeUrl'])
for t in json.load(sys.stdin)['data']['activeTargets'] if t['labels'].get('servidor')]
"
```

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `tools/storj_exporter.py` | Adicionados `storj_payout_current_gross_total_cents`, `storj_payout_current_repair_audit_cents`, `storj_payout_previous_repair_audit_cents`; fix do gross_total incluir repair_audit |
| `monitoring/prometheus.yml` | 3 scrape jobs para OrangePi (192.168.15.3) com `servidor: orangepi` |
