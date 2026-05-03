# Documentação Completa — Rebuy Lock + Testes + Deploy

Data: 2026-05-02
Repositório: eddie-auto-dev
Branch de trabalho: codex/ai-controls-max-positions
Branch de destino (deploy): main

## 1) Objetivo de negócio solicitado

Garantir regra rígida de recompra no agente de trading:

- Após uma venda, o próximo BUY só pode acontecer com preço estritamente menor que o preço médio de entrada da última posição vendida.
- Regra desejada: bloquear BUY quando `price >= last_sell_entry_price`.

## 2) Implementação aplicada

Arquivo principal alterado:

- `btc_trading_agent/trading_agent.py`

Trecho funcional aplicado em `_check_can_trade(signal)`:

- Quando `signal.action == "BUY"`:
- Lê `last_sell_entry_price` e posição atual (`position`).
- Aplica lock apenas quando não existe posição aberta (`current_pos <= 0`) e existe referência de última venda (`last_sell > 0`).
- Se `price >= last_sell`, bloqueia operação com motivo `buy_rebuy_lock_last_sell`.

Comportamento resultante:

- BUY com preço igual à última venda: bloqueado.
- BUY com preço acima da última venda: bloqueado.
- BUY com preço abaixo da última venda: permitido (desde que demais guardrails também permitam).

## 3) Persistência e ciclo da regra

- `last_sell_entry_price` é salvo após SELL para servir de referência de lock.
- `last_sell_entry_price` é limpo quando BUY válido é aceito.
- Recuperação de estado em startup usa histórico para restaurar lock quando necessário.

Impacto prático:

- Evita recompras no mesmo preço ou acima após encerramento de posição.
- Força reentrada com desconto real em relação à última posição vendida.

## 4) Testes unitários adicionados/ajustados

Arquivo de testes:

- `tests/test_rebuy_lock_enforcement.py`

Casos cobertos:

- `test_block_buy_when_price_not_lower_than_last_sell`: valida bloqueio para `price == last_sell_entry_price`.
- `test_allow_buy_when_price_lower_than_last_sell`: valida permissão para `price < last_sell_entry_price`.

Correção feita para estabilizar teste de permissão:

- Stub passou a mockar `_get_profile_buy_profit_guard_cfg` com edge mínimo em `0.0`, evitando bloqueio por outro guardrail não relacionado ao lock de recompra.
- Também foram adicionados stubs auxiliares (`_current_profile`, `_sync_target_sell_with_ai`) para isolar o teste da regra alvo.

## 5) Validação de testes executada

Suite de validação de trading executada e aprovada no fluxo da entrega, incluindo:

- `tests/test_rebuy_lock_enforcement.py`
- `tests/test_btc_valley_bounce.py`
- `tests/test_runtime_safety_guards.py`
- `tests/test_target_sell_price.py`
- `tests/test_ai_plan_sell_conditions.py`
- `tests/test_buy_profitability_guard.py`
- `tests/test_trailing_stop_and_auto_exit.py`
- `tests/test_ai_trade_window.py`

Resultado consolidado reportado durante a execução:

- 186 testes verdes no escopo de trading validado.

## 6) Versionamento e integração

Commit de entrega da regra:

- `041c7ad3` — `feat(trading): enforce strict rebuy lock — BUY only when price < last sell entry`

Fluxo aplicado:

- Commit na branch de trabalho.
- Merge fast-forward para `main`.
- Push para `origin/main`.

## 7) Deploy no homelab

Host de deploy:

- `homelab@192.168.15.2`
- Repositório remoto: `/home/homelab/myClaude`

Como o remoto tinha divergência local, foi adotada atualização cirúrgica de arquivos:

- Checkout de `origin/main` apenas para os arquivos da feature, sem reset destrutivo do repositório inteiro.

Validação de presença da regra em produção:

- Confirmada ocorrência de `buy_rebuy_lock_last_sell` no código remoto.

## 8) Restart e saúde dos serviços

Serviços reiniciados:

- `crypto-agent@BTC_USDT_aggressive`
- `crypto-agent@BTC_USDT_conservative`
- `crypto-agent@USDT_BRL_aggressive`
- `crypto-agent@USDT_BRL_conservative`

Estado após restart:

- Todos `active`.

Evidência de logs pós-restart:

- Inicialização concluída com sucesso (`Starting trading loop`, `Agent started`).
- Geração de plano AI ativa.
- Ajustes de regime ativos.
- Avisos pontuais `Price unavailable` observados em alguns ciclos, sem erro de execução do serviço.

## 9) Status final da entrega

Entrega concluída end-to-end:

- Regra de recompra estrita implementada.
- Testes da regra criados/corrigidos e passando.
- Merge e push para `main` concluídos.
- Deploy aplicado no homelab.
- Serviços críticos do trading ativos após restart.

## 10) Observações operacionais

- O lock rígido de recompra atua no cenário pós-venda sem posição aberta.
- Regras de DCA/valley-bounce para posição já aberta continuam independentes e não foram removidas.
- O ambiente contém mudanças locais em outros módulos não relacionadas diretamente a esta entrega; não foram revertidas nesta tarefa.
