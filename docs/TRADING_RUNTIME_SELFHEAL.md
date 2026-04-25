# Trading Runtime Self-Heal

Data: 2026-04-24  
Escopo: agents `crypto-agent@BTC_USDT_*` e `crypto-agent@USDT_BRL_*`

## Incidente que este self-heal evita

O incidente ocorreu porque a cópia antiga em `/home/homelab/eddie-auto-dev` não era mais o runtime real dos serviços. Os units ativos executavam a partir de `/apps/crypto-trader/trading/btc_trading_agent`, então mudanças aplicadas no path antigo não entravam em produção.

Também havia diretórios de runtime com ownership incorreto. O sintoma nos logs era `Permission denied` ao salvar arquivos do Market RAG em:

```text
/apps/crypto-trader/trading/btc_trading_agent/data/market_rag
```

Impacto observado:

- decisões novas continuavam sem `block_reason` enquanto o runtime real não tinha o patch;
- o agente não conseguia persistir parte do contexto RAG;
- o diagnóstico ficava confuso porque o path legado parecia atualizado, mas não era usado pelos serviços.

## O que foi adicionado

O exporter `grafana/exporters/trading_selfheal_exporter.py` agora valida e corrige a integridade do runtime:

- confirma que `/apps/crypto-trader/trading/btc_trading_agent` existe;
- valida marcadores de patch em `trading_agent.py` e `training_db.py`;
- verifica se `data/market_rag` está gravável;
- detecta se `/home/homelab/eddie-auto-dev` reapareceu;
- mede cobertura de `block_reason` em decisões recentes não-HOLD;
- corrige ownership/permissões de `data`, `data/market_rag` e `models`;
- remove o path legado se configurado;
- reinicia o unit afetado com rate limit.

## Métricas Prometheus

Endpoint: `http://<host>:9120/metrics`

Métricas novas:

```promql
trading_runtime_path_ok
trading_runtime_patch_ok
trading_market_rag_writable
trading_legacy_path_present
trading_block_reason_coverage_ratio
trading_runtime_selfheal_failures
```

Métricas já existentes continuam disponíveis:

```promql
trading_agent_up
trading_agent_stalled
trading_agent_last_decision_age_seconds
trading_agent_restart_total
trading_agent_consecutive_failures
```

Os labels usam o formato `SYMBOL:profile`, por exemplo `BTC-USDT:aggressive`.

## Dashboard Grafana

Dashboard criado:

```text
grafana/dashboards/trading-runtime-selfheal.json
```

Ele mostra:

- saúde geral dos agents;
- patch do runtime aplicado;
- gravabilidade do Market RAG;
- presença do path legado;
- cobertura de `block_reason`;
- idade da última decisão;
- contadores de restart/falha de self-heal.

## Serviço systemd

Unit:

```text
grafana/exporters/trading-selfheal-exporter.service
```

Runtime esperado em produção:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trading-selfheal-exporter
sudo systemctl status trading-selfheal-exporter --no-pager
```

O serviço roda como `root` porque precisa corrigir ownership, chmod, remover o path legado e reiniciar units `crypto-agent@*`. Os comandos de cura continuam auditados em:

```text
/var/lib/shared/trading-heal/trading_heal_audit.jsonl
```

## Verificação operacional

Status JSON:

```bash
curl -s http://localhost:9121/status | jq
```

Métricas principais:

```bash
curl -s http://localhost:9120/metrics | grep -E 'trading_runtime|trading_block_reason|trading_agent_up'
```

Logs:

```bash
journalctl -u trading-selfheal-exporter -n 100 --no-pager
journalctl -u 'crypto-agent@*' -n 100 --no-pager
```

Permissões esperadas:

```bash
namei -l /apps/crypto-trader/trading/btc_trading_agent/data/market_rag
sudo -u trading-svc test -w /apps/crypto-trader/trading/btc_trading_agent/data/market_rag
```

Path legado deve estar ausente:

```bash
test ! -e /home/homelab/eddie-auto-dev
```

## Alertas recomendados

Runtime sem patch:

```promql
min(trading_runtime_patch_ok) < 1
```

Market RAG sem escrita:

```promql
min(trading_market_rag_writable) < 1
```

Path legado recriado:

```promql
max(trading_legacy_path_present) > 0
```

Cobertura de motivo de bloqueio degradada:

```promql
min(trading_block_reason_coverage_ratio) < 0.8
```

Agent parado:

```promql
min(trading_agent_up) < 1
```

## Rollback

```bash
sudo systemctl disable --now trading-selfheal-exporter
sudo rm -f /etc/systemd/system/trading-selfheal-exporter.service
sudo systemctl daemon-reload
```

O rollback desativa apenas o self-heal. Ele não altera os units `crypto-agent@*` nem reverte os patches do trading agent.
