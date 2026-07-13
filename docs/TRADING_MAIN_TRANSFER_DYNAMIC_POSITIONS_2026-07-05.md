# Trading Agent — Transferência MAIN→TRADE e Posições Dinâmicas (2026-07-05)

Registro das melhorias aplicadas ao agente KuCoin (`btc_trading_agent`) para:

1. Detectar depósitos na conta **MAIN** durante o loop e transferir automaticamente para **TRADE**
2. Tornar o limite de **posições simultâneas** dinâmico conforme orientação da IA (RAG + Ollama)

**Arquivos alterados:**

| Arquivo | Mudança |
|---------|---------|
| `btc_trading_agent/trading_agent.py` | Sync MAIN→TRADE no loop; `_resolve_trade_controls` dinâmico |
| `btc_trading_agent/market_rag.py` | `ai_max_entries` escala com saldo alto |
| `tests/test_main_transfer_and_dynamic_positions.py` | Regressões |

---

## Contexto

### Problema 1 — Depósito só visível após restart

Depósitos fiat (PIX/BRL) e crypto caem na conta **MAIN** da KuCoin. O agente opera e consulta saldo apenas na conta **TRADE**.

Antes, a transferência `MAIN → TRADE` (`_auto_transfer_and_sync`) rodava **somente no bootstrap** (startup/restart do processo). Se o usuário depositasse com o agente já rodando, o BRL ficava na MAIN até o próximo restart.

### Problema 2 — `max_positions` fixo no config

Perfis como `config_USDT_BRL_conservative.json` definem `max_positions: 1`. Mesmo com a IA (RAG) sugerindo 12+ entradas DCA (`ai_max_entries`), o agente bloqueava novas compras com `buy_max_positions`.

---

## 1. Transferência MAIN→TRADE no loop

### Comportamento

- A cada `main_transfer_check_cycles` ciclos do loop (padrão: **3** × `poll_interval` ≈ **15s**), o agente chama `_auto_transfer_and_sync()`.
- Se houver saldo na MAIN para a moeda base ou quote do par (ex.: USDT e BRL em `USDT-BRL`), transfere tudo para TRADE via `inner_transfer`.
- Após transferência bem-sucedida:
  - loga: `Depósito detectado na MAIN — saldo transferido para TRADE e liberado para negociação`
  - executa `_detect_external_deposits()` para reconciliar depósitos de crypto

### Config opcional

```json
{
  "poll_interval": 5,
  "main_transfer_check_cycles": 3
}
```

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `main_transfer_check_cycles` | `3` | Intervalo em ciclos entre checagens MAIN→TRADE |

### Fluxo

```
Depósito PIX/Fiat ou crypto → MAIN
        ↓
Loop (~15s): _auto_transfer_and_sync()
        ↓
inner_transfer(main → trade) para USDT e/ou BRL
        ↓
Saldo disponível para ordens na TRADE
```

### Função alterada

`_auto_transfer_and_sync()` agora retorna `bool` — `True` se ao menos uma transferência foi concluída.

---

## 2. Limite de posições dinâmico (IA)

### Comportamento

`_resolve_trade_controls()` passou a usar **`ai_max_entries`** (calculado pelo RAG em `_calculate_ai_position_size`) como referência operacional, em vez do valor fixo do JSON.

| Fonte | Papel |
|-------|-------|
| `ai_max_entries` (RAG) | Limite operacional principal (4–24 conforme regime, vol, saldo) |
| `applied_max_positions` (Ollama, modo `apply`) | Ajuste fino quando `similar_count >= 3` |
| `max_positions` (config JSON) | Teto de segurança mínimo; **não bloqueia** a IA quando conservador (ex.: 1) |
| `MAX_POSITIONS` (config global) | Teto absoluto do perfil |

### Escala por saldo (market_rag)

`_calculate_ai_position_size` ganhou tiers adicionais:

| Saldo (quote) | Efeito em `ai_max_entries` |
|---------------|----------------------------|
| < R$ 20 | Cap em 6 entradas |
| ≥ R$ 200 | Mínimo 10 entradas |
| ≥ R$ 1000 | Escala até 24 entradas |

### Exemplo prático

Config `USDT-BRL conservative` com `max_positions: 1`:

- **Antes:** máximo 1 entrada DCA, independente da IA
- **Depois:** IA pode orientar 12 entradas em mercado bearish; Ollama em `apply` pode reduzir para 8

Logs periódicos exibem: `risk_cap=15.0%/12` (exposição % / slots efetivos).

---

## 3. O que NÃO mudou

- **Geração de PIX** para depositar na KuCoin continua **somente pelo app/site** — não há endpoint público na API KuCoin.
- Transferência MAIN→TRADE **não** força compra; apenas libera saldo para o agente operar quando houver sinal.
- Guardrails (cooldown, confiança mínima, buy target da IA) permanecem ativos.

---

## 4. Testes

```bash
python3 -m pytest tests/test_main_transfer_and_dynamic_positions.py -q
```

Cobertura:

- `_auto_transfer_and_sync` retorna `True`/`False` corretamente
- `_resolve_trade_controls` usa `ai_max_entries` acima do config fixo
- Ollama `apply` combina cap da IA com sugestão Ollama
- RAG escala `ai_max_entries` com saldo alto

---

## 5. Deploy

Após merge, reiniciar os agents afetados:

```bash
systemctl restart crypto-agent@USDT_BRL_conservative
systemctl restart crypto-agent@USDT_BRL_aggressive
# demais pares live conforme frota
```

Verificar logs:

```bash
journalctl -u crypto-agent@USDT_BRL_conservative -f | grep -E 'Auto-transferred|MAIN|max_positions|risk_cap'
```

---

## Referências

- `DEPOSIT_DETECTION_FIX_2026-04-25.md` — MAIN vs TRADE, detecção de fiat
- `docs/TRADING_AGENT_REVIEW_2026-07-03.md` — painel Grafana saldo R$
- KuCoin PIX deposit (manual): [How to Deposit BRL Using Pix](https://www.kucoin.com/support/7542840596377)