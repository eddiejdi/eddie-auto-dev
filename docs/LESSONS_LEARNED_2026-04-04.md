# Lições Aprendidas — 2026-04-04

**Tema:** Restauração de conectividade do nó Storj em topologia Double-NAT

---

## 1. Contexto

O nó Storj (`storagenode`, IP macvlan `192.168.15.250`) perdeu conectividade com os satélites após uma queda de energia que reiniciou o roteador TP-Link TL-WR740N. A regra de port-forward `28967 → 192.168.15.250` não sobreviveu ao ciclo de energia no roteador intermediário, e o sistema ficou offline.

Topologia descoberta (Double-NAT):
```
Internet (191.202.237.52:28967)
  └─ ZTE GPON (WANpub → 192.168.14.1)
       └─ TP-Link TL-WR740N (WAN: 192.168.14.2 / LAN: 192.168.15.1)
            └─ Homelab Server (192.168.15.2)
                 └─ Storj macvlan (192.168.15.250:28967)
```

---

## 2. Causas-raiz identificadas

### 2.1 Double-NAT não mapeado nos runbooks anteriores
- Sistema assumia NAT único (ZTE → Homelab). Havia um segundo roteador intermediário (TP-Link TL-WR740N) com NAT próprio.
- Regras do ZTE apontavam para `192.168.14.2` (WAN do TP-Link) em vez de `192.168.15.250` diretamente.
- **Ambos** os roteadores precisam de port-forward 28967 configurados.

### 2.2 TP-Link TL-WR740N HTTPD efêmero
- O servidor HTTP do roteador fica **ativo por apenas ~60-120 segundos** após power-cycle.
- Scripts Selenium muito lentos para completar o fluxo nessa janela.
- Abordagem via **HTTP direto com campos GET corretos** é a única viável.

### 2.3 Campos de formulário errados (3 tentativas para acertar)
- Tentativa 1: campos `ip/port/localPort/protocol` → **ERRO errCode 14001**
- Tentativa 2: campos `Addnew/Enall/Disall` → eram botões da página de lista, não do form de adição
- Tentativa 3 (✅): campos reais descobertos ao GET `?Add=Add&Page=1`:
  - `ExPort`, `InPort`, `Ip`, `Protocol` (1=ALL), `State`, `Changed`, `SelIndex`, `Page`, `Save`

### 2.4 Método HTTP incorreto
- O formulário HTML usa `method="get"`, mas a tentativa inicial foi via POST → retorna **501 Not Implemented**
- Regra adicionada via GET com todos os parâmetros na query string.

### 2.5 Backoff do Storj após 12 falhas consecutivas
- Após 12 pings falhos, o Storj espera até **1 hora** para tentar novamente.
- Solução: `docker restart storagenode` para resetar os contadores internos.
- Confirmação de sucesso: `node scores updated` nos logs em ~90s.

### 2.6 Selfheal exporter não detectou o problema
- `storj-selfheal-exporter.service` tem flag `recreate_on_address_drift` — pode recriar container ao detectar drift de IP.
- Durante outage completo, o próprio exporter pode parar de coletar (sem acesso aos satélites).
- Não confiar no exporter para detecção de double-NAT quebrado.

---

## 3. Correções aplicadas

| Item | Ação | Status |
|------|------|--------|
| ZTE GPON port-forward | TCP+UDP 28967 → 192.168.14.2 | ✅ Persistente |
| TP-Link port-forward | 28967 ALL → 192.168.15.250 via GET URL correta | ✅ Confirmado |
| Script de autoconfig | `/tmp/tplink_pf_direct.py` (v3) com campos e método corretos | ✅ Funcional |
| Storj restart | `docker restart storagenode` para zerar backoff | ✅ Feito |
| Serviço systemd temporário | `tplink-portforward.service` criado e removido após uso | ✅ Limpo |
| Online scores | Recuperando (0.73–0.85) após período offline | ⏳ Em progresso |

---

## 4. Resultados

Todos os 4 satélites confirmaram `node scores updated` às 19:06Z UTC (2026-04-04):

| Satélite | online_score |
|----------|-------------|
| `1wFTAgs9DP5RSnCqKV1eLf6N9wtk4EAtmN5DpSxcs8EjT69tGE` | 0.8221 |
| `121RTSDpyNZVcEU84Ticf2L1ntiuUimbWgfATz21tuvgk3vzoA6` | 0.8462 |
| `12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S` | 0.7287 |
| `12L9ZFwhzVpuEKMUNUqkaTLGzwY9G24tbiigLiXpmZWKwmcNDDs` | 0.8180 |

---

## 5. Referências técnicas confirmadas

### TP-Link TL-WR740N — Port Forward Virtual Server
```
# Adicionar regra (GET — não POST):
GET http://192.168.15.1/userRpm/VirtualServerRpm.htm?ExPort=28967&InPort=28967&Ip=192.168.15.250&Protocol=1&State=1&Changed=0&SelIndex=0&Page=1&Save=Save
Authorization: Basic YWRtaW46YWRtaW4=  # admin:admin

# Verificar regra:
GET http://192.168.15.1/userRpm/VirtualServerRpm.htm?Page=1
# IP 192.168.15.250 deve aparecer no HTML

# Protocol values:
# 1 = ALL, 2 = TCP, 3 = UDP
```

### Script de recuperação (caso regra seja perdida novamente)
```bash
# Verificar se TP-Link está up (executa no homelab):
timeout 4 bash -lc "</dev/tcp/192.168.15.1/80" && echo UP || echo DOWN

# Aplicar regra (durante janela ~60-120s após power-cycle):
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 'python3 /tmp/tplink_pf_direct.py'

# Verificar Storj após configuração:
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 \
  'docker logs --since 90s storagenode 2>&1 | grep "node scores updated"'

# Se Storj em backoff (>12 falhas):
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 'docker restart storagenode'
```

### Storj config
- Config file (host): `/mnt/disk3/storj/data/config.yaml`
- Config file (container): `/app/config/config.yaml`
- `contact.external-address: 191.202.237.52:28967`
- Console local: `http://127.0.0.1:14002/api/sno` (do homelab)
- Rede Docker: `storj_macvlan` (macvlan driver)

---

## 6. Prevenções e recomendações

1. **Documentar Double-NAT no runbook de recuperação** — qualquer restart do TP-Link requer reconfigurar port-forward.
2. **TP-Link HTTPD efêmero**: manter script `/tmp/tplink_pf_direct.py` ativo no homelab; considerar UPS para evitar power-cycles não planejados.
3. **Monitoramento**: criar alerta Grafana/Prometheus quando `storj_tcp_ok` ou `storj_quic_ok` ficarem 0 por >5min.
4. **Storj backoff**: alertar em Telegram quando `ping satellite failed` aparecer nos logs consecutivamente.
5. **Selfheal exporter**: definir `recreate_on_address_drift: false` no `/etc/eddie/storj_selfheal.json` para evitar recreações automáticas indesejadas durante investigação.
6. **Secrets vault**: credenciais do ZTE já estão no vault (`network/zte_gpon_modem`); adicionar `network/tplink_router_001` se ainda não houver.

---

## 7. Arquivos relevantes

| Arquivo | Descrição |
|---------|-----------|
| `/workspace/eddie-auto-dev/tmp/tplink_pf_direct.py` | Script v3 — configurador HTTP do TL-WR740N |
| `/home/homelab/eddie-auto-dev/grafana/exporters/storj_selfheal_exporter.py` | Selfheal exporter |
| `/mnt/disk3/storj/data/config.yaml` | Config do nó Storj |
| `/etc/eddie/storj_selfheal.json` | Config do selfheal exporter |

---

## 8. Referências cruzadas

- [HOMELAB_INFRASTRUCTURE_DIAGRAMS.md](HOMELAB_INFRASTRUCTURE_DIAGRAMS.md) — Diagrama de rede atualizado
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Checklist geral de troubleshooting
- [docs/SERVER_CONFIG.md](SERVER_CONFIG.md) — Configuração de serviços do homelab
- Memória repo: `/memories/repo/network-infrastructure.md`
- Memória repo: `/memories/repo/tplink-device-config.md`
