# Comunicado Semanal — Eddie Auto-Dev
**Período:** 10/02/2026 → 17/02/2026  
**Gerado:** 17/02/2026 17:05 UTC  
**Enviado via:** Telegram (chat_id: 948686300, 3 mensagens)

---

## 1. Estou-Aqui App (repo: eddiejdi/estou-aqui)

| Entrega | Branch/PR |
|---------|-----------|
| Webchat widget com integração Telegram | fix/alert-bus-fallback |
| Endpoint beta-signup + landing page | fix/alert-bus-fallback |
| Suporte a passeata (início/chegada) | fix/alert-bus-fallback |
| Chat de grupo Telegram para eventos | fix/alert-bus-fallback |
| CI Flutter atualizado para v3.38.9 | fix/alert-bus-fallback |
| Pipeline alerting E2E (Grafana → Backend → Bus → Agent) | fix/alert-bus-fallback |
| Fallback host-gateway para Agent Bus | fix/alert-bus-fallback |
| Métricas Prometheus no backend | fix/alert-bus-fallback |
| PR #9 — alert bus fallback | Em revisão |

**Commits:** 21 commits no período

---

## 2. Homelab / myClaude (repo: eddiejdi/eddie-auto-dev)

| Entrega | PR |
|---------|-----|
| Home Assistant integrado ao WhatsApp bot | merged |
| NL parser melhorado (fuzzy device matching) | merged |
| Secrets audit + migration | PR #67 merged |
| Cloudflare Tunnel documentação atualizada | merged |
| CV skills extraction com Docling | merged |
| ML-first job application system | merged |
| RAG expandido: 2 → 268 documentos | merged |

**Commits:** 15 commits no período

---

## 3. AutoCoinBot (BTC Trading Agent)

### 3.1 Migração SQLite → PostgreSQL
- **264.722 registros** migrados em 6 tabelas:
  - trades: 2.750
  - decisions: 163.425
  - market_states: 98.544
  - learning_rewards: 0
  - performance_stats: 3
  - candles: 0
- **Integridade validada:** PnL SQLite = $51.0441 = PnL PostgreSQL
- **9 arquivos patcheados:** training_db.py, trading_engine.py, webui_integration.py, prometheus_exporter.py, daily_report.py, btc_query.py, monitor_agent.py, backtest.py, openwebui_tool.py
- **0 referências a sqlite3** no codebase ativo
- **Backup:** trading_agent_pre_pg_20260217.db + training_db_sqlite.py.bak
- **PostgreSQL:** schema btc.*, psycopg2 ThreadedConnectionPool(1,5)

### 3.2 Status do Modelo Q-Learning
| Métrica | Valor |
|---------|-------|
| Episodes | 72.188 |
| Q-table preenchida | 45.8% (1.374/3.000) |
| Total reward | 58.84 |
| Win rate | 55.6% (tendência: 48.9% → 59.4%) |
| PnL bruto | +$53.36 |
| Volume total | $241.542 |
| Fees estimadas (0.2% ida+volta) | -$483 |
| **PnL líquido** | **-$430** |
| Avg PnL/trade | $0.037 |
| Avg fee/trade | $0.351 |

### 3.3 Otimizações de Profitabilidade Aplicadas
| Parâmetro | Antes | Depois |
|-----------|-------|--------|
| min_confidence | 0.35 (config) / 0.50 (code) | **0.70** |
| min_trade_interval | 180s (config) / 60s (code) | **600s** |
| max_daily_trades | 15 | **8** |
| take_profit_pct | 3% | **5%** |
| strategy.mode | scalping | **swing** |
| rsi_oversold/overbought | 35/65 | **30/70** |
| min_spread_bps | 5 | **10** |

### 3.4 Previsão de Confiabilidade
- **Checkpoint 1** (~1 semana): Validar redução de trades e aumento de avg PnL
- **Checkpoint 2** (~2-3 semanas): Q-table >70%, win rate estável
- **Minimamente confiável:** ~4-6 semanas
- **Confiável para real:** ~8-12 semanas

---

## 4. Infraestrutura

### Serviços Systemd (8/8 ativos)
- btc-trading-agent ✅
- btc-trading-engine ✅
- btc-engine-api (:8511) ✅
- btc-webui-api (:8510) ✅
- secrets-agent (:8088) ✅
- specialized-agents-api (:8503) ✅
- eddie-telegram-bot ✅
- ollama (:11434) ✅

### Containers Docker (23 ativos)
- eddie-postgres, grafana, loki, promtail
- open-webui, openwebui-postgres
- homeassistant (unhealthy), waha
- cadvisor, node-exporter
- nextcloud-app, nextcloud-db, nextcloud-redis, nextcloud-cron
- homelab-copilot-agent
- 5x specialized agents (python, go x2, php x2, rust x2)

### Recursos do Servidor
- RAM: 23/31 GB (74%)
- Disco: 131/232 GB (60%)
- Load average: 8.10 (8 cores)
- Uptime: 1 dia, 5h (reiniciado 16/02)

### Riscos Identificados
1. **Load alto (8.10)** — próximo do limite, monitorar OOM
2. **Home Assistant unhealthy** — requer investigação
3. **AutoCoinBot capital insuficiente** — $8.15 na KuCoin

---

## 5. Processo de Documentação

Este relatório foi gerado pelo Copilot Agent (local) com dados coletados de:
1. PostgreSQL (btc.* schema) — métricas do AutoCoinBot
2. systemctl is-active — status dos serviços
3. docker ps — containers ativos
4. free -h, df -h, uptime — recursos do servidor
5. git log --since="2026-02-10" — commits dos repos
6. Análise do modelo Q-Learning (qmodel_BTC_USDT.pkl)

Enviado via Telegram Bot API em 3 mensagens (limite 4096 chars/msg).
