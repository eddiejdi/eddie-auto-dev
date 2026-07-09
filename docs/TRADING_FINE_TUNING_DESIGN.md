# Design: Fine-tuning do modelo de trading a partir de decisões históricas

Status: proposta de design, não implementado. Nenhum código deste documento está em produção.

## 1. Motivação

Hoje o "aprendizado" do Trading Agent é 100% feedback textual + gates determinísticos:

- `_fetch_db_perf_context()` (`btc_trading_agent/trading_agent.py:824`) injeta win_rate/PnL dos últimos 7 dias no `CONTEXT` enviado ao Ollama antes de cada decisão (`trading_agent.py:2059`).
- Gates hard-coded consomem o mesmo histórico: `_get_profile_buy_profit_guard_pressure()` (aperta o edge mínimo para BUY conforme losing streak) e `_analyze_signal_context()` (penaliza/bonifica com base no PnL não-realizado da posição aberta).
- Não há nenhum ajuste de pesos do modelo — o histórico só entra via prompt e via lógica de config (`guardrails_positive_only_sells`).

Fine-tuning move parte desse aprendizado para os pesos do LLM: o modelo aprende diretamente, a partir de decisões passadas + resultado real, em vez de depender só do prompt "lembrar" corretamente a cada chamada.

## 2. Topologia

```
[HOMELAB 192.168.15.2]                         [NAS 192.168.15.4 — nas-optiplex]
GPU: RTX 3060 11GB (produção, trading-analyst)  GPU: RTX 2060 SUPER 8GB (livre, sem isolamento)
Postgres: btc.trades / btc.decisions /          CPU: Intel i3-3220 (2C/4T) — fraco
          btc.learning_rewards                  RAM: 8GB — fraco
                                                 SO: TrueNAS-SCALE-24.10.2.4
```

A 3060 continua servindo produção sem ser tocada. Todo o trabalho de dataset, treino e shadow-serving roda na 2060 do NAS.

## 3. Pipeline

```
btc.decisions + btc.trades + btc.learning_rewards   (Postgres, homelab)
        │
        ▼
[1-4] Dataset builder — roda NO HOMELAB (CPU melhor, acesso direto ao Postgres)
      junta decisão executada → trade → resultado real (pnl_pct)
      formato de prompt IDÊNTICO ao usado em produção (trading_agent.py:2061)
      filtro: só decisões executed=True, reward não-nulo, N mínimo por profile
        │
        │ dataset final (JSONL) — única transferência para o NAS
        ▼
[5] Treino QLoRA 4-bit — roda no NAS (TrueNAS App, container com GPU 0000:01:00.0 reservada)
      base = mesmo modelo aprovado em uso em produção (gemma3/phi3/mistral-7b)
      batch pequeno + sequence length enxuto (CPU/RAM do NAS são o limite, não a VRAM)
        │
[6] Merge LoRA + conversão GGUF (no NAS)
        │
[7] Ollama local no NAS, tag nova (ex: trading-analyst:v2-ft-2026wXX)
        │
[8] Shadow mode — candidato roda na 2060 do NAS
      recebe o MESMO fluxo de contexto de mercado que a produção (3060)
      gera decisões só para log/comparação — NUNCA executa ordem real
        │
        ▼ (comparação assíncrona, homelab)
[9] Métricas: win_rate, avg_pnl, drawdown simulado, taxa de concordância com produção
        │
[10] Promoção manual (via approval gateway / Telegram) — nunca automática
```

## 4. Dataset — formato

Reaproveitar o schema já existente em `training_db.py` em vez de criar um novo:

```python
{
  "prompt": <prompt estruturado idêntico ao de produção, incl. bloco CONTEXT/HISTÓRICO DB>,
  "completion": {"action": ..., "confidence": ..., "reason": ...},
  "reward": <pnl_pct real, ou reward contrafactual de gate>,
  "profile": "BTC_USDT" | "ETH_USDT" | ...,
  "executed": true
}
```

Crítico: o prompt de treino precisa ser byte-a-byte igual ao de produção (mesmo `CONTEXT`, mesmo bloco "HISTÓRICO DB (últimos 7 dias)"). Se o template de prompt mudar em produção sem versionar o dataset junto, o fine-tuning aprende um padrão que não existe em runtime.

## 5. Reward shaping

Reaproveitar `_retro_score_sample()` (`training_db.py:866-989`, hoje sem nenhum treino real consumindo sua saída):

- Decisão respeitou gates (`profit_guard`, `guardrails_positive_only_sells`) e deu lucro → reward alto.
- Gate bloqueou corretamente uma perda (contrafactual, sem trade executado) → reward positivo mesmo sem execução.
- HOLD correto em mercado lateral → reward neutro-positivo (evita viés de sempre recomendar trade).

## 6. Avaliação e promoção (gate humano obrigatório)

Nunca promover automaticamente — consistente com a regra já existente de que trading BTC/ETH não inicia sem revisão humana (dinheiro real, `dry_run=False`).

1. Backtest offline (replay histórico, sem execução).
2. Shadow mode em produção (passo 8), N dias mínimo.
3. Comparação de métricas: win_rate, avg_pnl, drawdown, concordância com modelo atual.
4. Aprovação humana explícita via approval gateway (Telegram) antes de trocar a tag do modelo em uso pela 3060.

## 7. Rollback

Tag anterior do modelo permanece intacta no Ollama de produção. Troca é só mudar uma referência de tag/env — reversível em segundos, sem sobrescrita destrutiva.

## 8. Restrições de hardware conhecidas (NAS)

- CPU i3-3220 (2C/4T) e 8GB RAM: dataloader/tokenização serão lentos. Preparo pesado do dataset (passos 1-4) fica no homelab; o NAS só recebe o JSONL pronto.
- GPU RTX 2060 SUPER 8GB: confortável para QLoRA 4-bit em modelos de até 7B com batch pequeno e sequence length enxuto.
- GPU hoje sem isolamento (`isolated_gpu_pci_ids: []`) e sem apps rodando — livre para reservar via TrueNAS App.
- NAS também roda drives LTO (sg3/sg5) com operações de fita que já causaram incidentes de disco cheio ([[project_lto_nas_root_full_20260531]], [[project_lto_nas_root_full_20260601]]) — treino/checkpoints precisam de gate de espaço em disco dedicado, separado do pool de fita/backup.

## 9. Riscos a vigiar

- **Overfitting em poucos trades**: volume de trades reais é baixo; exigir mínimo de amostras (ex. >200 decisões executed por profile) antes do primeiro treino.
- **Data leakage temporal**: split estritamente cronológico, nunca treinar com dados futuros relativos ao ponto de decisão.
- **Drift de prompt**: versionar o template de prompt junto com cada dataset de treino.
- **Contenção com fita**: agendar treino fora das janelas de flush/drain de LTO no NAS.

## 10. Correções pós-exploração do código (2026-07-06)

A exploração do código real ajustou três premissas do desenho original:

1. **Nenhum LLM decide BUY/SELL/HOLD.** Isso é 100% determinístico
   (`_analyze_signal_context`, gates de profit guard). O Ollama só é consultado em
   3 pontos: **trade controls** (`trading_agent.py:2061`, JSON de parâmetros de
   risco), **trade window** (`trading_agent.py:2261`, JSON de banda de preço) e
   **AI plan** (`trading_agent.py:2763`, texto livre PT-BR). O fine-tuning tem esses
   3 contratos como alvo.
2. **As saídas já eram parcialmente persistidas**, mas não serviam de dataset: as
   tabelas `btc.ai_trade_controls` / `btc.ai_trade_windows` / `btc.ai_plans` guardam
   a saída **já parseada**, sem o prompt/CONTEXT exato nem o texto livre do plano —
   que é o que o SFT precisa. Por isso a Fase 1 cria `btc.llm_calls` (prompt+resposta
   bruta), complementando as tabelas existentes em vez de duplicá-las.
3. **O endpoint da NAS já estava antecipado** em `btc_trading_agent/llm.py`
   (`nas-rtx2060`, `LLM_NAS_HOST`, default `http://192.168.15.4:11546`/`:11436`),
   hoje fora do ar — a Fase 5 completa essa infra já planejada.

## 11. Status de implementação (2026-07-06)

| Fase | Entregável | Arquivo | Estado |
|------|-----------|---------|--------|
| 1 | Tabela + métodos de log | `btc_trading_agent/training_db.py` (`llm_calls`, `record_llm_call`, `get_llm_calls`, `prune_llm_calls`) | **feito** |
| 1 | Captura best-effort das 3 chamadas | `btc_trading_agent/trading_agent.py` (`_record_llm_call` + 3 call sites) | **feito** |
| 1 | Testes (mock Postgres, não-bloqueante) | `tests/test_llm_calls_logging.py` (6 testes) | **feito, verde** |
| 2 | Dataset builder | `scripts/trading_analyst_finetune_dataset_builder.py` | **feito** (aguarda dados) |
| 4 | Treino QLoRA na NAS (multi-task) | `scripts/trading_analyst_finetune_batch.py` | **feito** (aguarda dataset + venv NAS) |
| 6 | Shadow evaluator (só-leitura) | `scripts/trading_analyst_shadow_eval.py` | **feito** (aguarda candidato) |
| 7 | Relatório comparativo | `scripts/trading_analyst_shadow_eval.py --report` | **feito** |
| 3 | Spike GPU na NAS (Custom App) | — | **gate**: muta a NAS |
| 5 | Ollama servindo na NAS | — | **gate**: muta a NAS |
| 1→prod | Deploy do log nos `crypto-agent@*` | — | **gate**: reinício de serviços de trading real |

### Bloqueio natural do pipeline

Fases 4/6/7 não podem **rodar até o fim** hoje: o log da Fase 1 ainda não está em
produção, então `btc.llm_calls` está vazio e não há dataset. O caminho real é:
deployar a Fase 1 → acumular semanas de dados → rodar a Fase 2 → só então treinar
(Fase 4), servir (Fase 5) e comparar em shadow (Fase 6/7). Todos os **códigos** estão
prontos; o que falta são ações que mutam produção/NAS, deixadas para o gate humano.

### Painel de controle da Fase 1 (runtime, ligar/desligar + parametrizar)

O log de LLM é controlável em runtime, sem redeploy, por um painel em JS:

- Config no DB: `btc.llm_log_config` (linha única) — `enabled`, toggles por call_type
  (`log_controls`/`log_window`/`log_plan`), `sample_rate` (fração gravada),
  `max_prompt_chars` (truncagem), `prune_days` (retenção). Métodos
  `get_llm_log_config`/`set_llm_log_config`/`get_llm_call_stats` em `training_db.py`.
- Agente: `_record_llm_call` consulta a config com **cache de 30s** e respeita
  enabled/toggle/sample/truncagem — tudo best-effort (falha de config → defaults →
  nunca afeta trading).
- Backend: `scripts/llm_log_panel_server.py` (`GET/POST /api/config`, stats ao vivo,
  API key opcional via `PANEL_API_KEY`).
- Frontend: `scripts/llm_log_panel/index.html` + `llm_log_panel.js` (toggles,
  sliders, estatísticas de `btc.llm_calls`). Unit: `systemd/llm-log-panel.service`.
- Testes: `tests/test_llm_log_panel_server.py` (5) + gating em
  `tests/test_ai_trade_window.py` (5) + config em `tests/test_llm_calls_logging.py`.

Fluxo completo da Fase 1 (log + controle) está pronto e verde. As mudanças só passam
a ter efeito quando os serviços `crypto-agent@*` forem reiniciados em produção — o
gate humano descrito acima.

### Correção adjacente

Durante o trabalho, 5 testes pré-existentes de `tests/test_ai_trade_window.py`
estavam quebrados por drift após o refactor para `LLMRouter` (testavam o antigo
`_request_ollama_structured` que fazia httpx próprio; hoje ele só delega para
`self._llm.request_structured`). Foram reescritos para o contrato atual — a lista
de CI de BTC voltou a 100% verde (185 testes).
