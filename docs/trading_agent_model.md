**Visão Geral**
- **Resumo:** Documento breve que descreve o modelo de trading, arquitetura e pipeline de treinamento usados no repositório.

**Modelo Principal**
- **Tipo:** Q‑learning tabular (implementado como `FastQLearning` em [btc_trading_agent/fast_model.py](btc_trading_agent/fast_model.py)).
- **Formato:** Tabelas Q por símbolo, ações discretas: `HOLD=0`, `BUY=1`, `SELL=2`.
- **Armazenamento:** Q‑tables serializadas em `btc_trading_agent/models/` (ex.: `fast_model_{SYMBOL}.pkl`).

**Ensemble de Decisão**
- **Componente:** `FastTradingModel` combina múltiplos sinais.
- **Pesos padrão:** technical=0.35, orderbook=0.30, flow=0.25, qlearning=0.10.
- **Thresholds:** buy/sell thresholds e `min_confidence` configuráveis em `fast_model.py`.

**Pipeline de Treinamento**
- **Script principal:** [btc_trading_agent/train_with_ollama.py](btc_trading_agent/train_with_ollama.py).
- **Abordagem:** usa o motor Ollama (LLM) para analisar janelas de mercado e gerar regras/insights, que são então usados para atualizar as Q‑tables tabulares.
- **Motivação:** aproveitar a GPU via Ollama sem reimplementar modelo em PyTorch.

**Dependências e Ambiente**
- **Ollama:** executando em homelab `http://localhost:11434` (ex: `qwen2.5-coder:7b`).
- **Banco de dados:** PostgreSQL (schema `btc`) — tabelas relevantes: `ollama_analyses`, `ollama_trading_rules`, `candles`, `agent_state`.
- **Python:** exige `numpy`, `psycopg2`, `httpx`/`requests` (ver ambiente virtual do projeto `.venv`).

**Arquivos-chave**
- [btc_trading_agent/fast_model.py](btc_trading_agent/fast_model.py): classes `FastQLearning`, `FastIndicators`, `FastTradingModel`.
- [btc_trading_agent/train_with_ollama.py](btc_trading_agent/train_with_ollama.py): pipeline que consulta Ollama e atualiza Q‑tables.
- `btc_trading_agent/models/`: local onde os `.pkl` são salvos e carregados.

**Como rodar (exemplo no homelab)**
1. Ative venv no homelab na pasta do projeto:

```bash
source /home/edenilson/eddie-auto-dev/.venv/bin/activate
cd ~/eddie-auto-dev/btc_trading_agent
```

2. Rodar o pipeline de treinamento (nohup/ssh recomendado para execução longa):

```bash
nohup python3 train_with_ollama.py --symbols BTC-USDT,ETH-USDT --epochs 5 > train_ollama.log 2>&1 &
```

3. Verificar modelos gerados:

```bash
ls -la btc_trading_agent/models/fast_model_*.pkl
psql "$DATABASE_URL" -c "SELECT count(*) FROM ollama_analyses;"
```

**Observações Operacionais**
- Ollama pode devolver `null` em campos numéricos; o pipeline faz sanitização (`safe_float`) antes de persistir.
- O modelo `FastQLearning` é CPU‑bound (numpy). O uso da GPU é feito indiretamente via Ollama para análise/geração de regras.
- Ajustar timeouts de requests ao Ollama (ex: 300s) para evitar falhas em janelas grandes.

**Próximos passos (sugestões)**
- Integrar as regras geradas pelo Ollama no runtime do `FastTradingModel` (aumentar peso do componente LLM).
- Backtest dos Q‑tables gerados contra janelas históricas antes de aplicar em produção.
- Agendar retraining periódico (systemd/cron) no homelab.

**Contato/Referências**
- Código relevante: [btc_trading_agent/fast_model.py](btc_trading_agent/fast_model.py), [btc_trading_agent/train_with_ollama.py](btc_trading_agent/train_with_ollama.py).

---
Documento gerado automaticamente pelo assistente — edições manuais bem‑vindas.
