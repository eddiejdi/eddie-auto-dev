# Relatório: Causa dos Gaps na Negociação do Agent

Data: 12 de maio de 2026
Escopo: verificar se falta de espaço foi causa dos gaps, com foco no comportamento do agent.

## Resumo Executivo
A falta de espaço em disco impactou o agent (erro ENOSPC confirmado), mas não explica sozinha os gaps observados. A causa é multifatorial, com três vetores principais:

1. indisponibilidade operacional do agent em janelas específicas;
2. bloqueio recorrente de SELL por guardrail de PnL mínimo;
3. instabilidade do endpoint de IA (HTTP 503) com fallback frequente.

## Evidências Coletadas

### 1) Falta de espaço afetando o agent
Evidência direta em logs do serviço:

- `OSError: [Errno 28] No space left on device`
- `Failed to save AI trade window: [Errno 28] No space left on device`

Ocorrência confirmada em perfis BTC-USDT (conservative e aggressive) por volta de 08:13 (12/05/2026).

Conclusão: houve impacto real no processamento/registro de janelas de trade.

### 2) Janela sem atividade operacional dos serviços
Na janela 2026-04-28 até 2026-05-09:

- `crypto-agent@BTC_USDT_conservative.service`: sem entradas no journal (`-- No entries --`)
- `crypto-agent@BTC_USDT_aggressive.service`: sem entradas no journal (`-- No entries --`)

Além disso, os units atuais mostram início recente em 12/05 (08:03 a 08:33), indicando descontinuidade operacional antes desse ponto.

Conclusão: parte dos gaps coincide com período sem atividade observável do agent.

### 3) Bloqueio de SELL por guardrail
Logs recorrentes:

- `Guardrail blocked sub-threshold SELL ... (-1.43% < 0.30%)`

Isso impede saída de posição em múltiplos ciclos, reduzindo realização de trades mesmo com sinais de SELL.

Conclusão: guardrail está funcionando conforme regra, porém contribuindo para baixa execução de SELL em cenário adverso.

### 4) Instabilidade do endpoint de IA
Logs recorrentes:

- `HTTP Request ... 503 Service Unavailable` no endpoint `:11437`
- geração de `AI trade window [fallback] ... reason=RuntimeError`

Conclusão: quando o endpoint falha, o agent entra em fallback, com impacto na qualidade/consistência da tomada de decisão.

### 5) Evidência no fluxo de trades
Histórico recente de `executed` mostra atividade concentrada após retorno operacional, com lacunas entre dias. Exemplo no período 25/04-12/05:

- sem trades em alguns dias da janela;
- retomada com aumento de execução em 10-11/05;
- USDT-BRL permanece com BUYs sem SELL (posição aberta sem realização).

## Diagnóstico Final
A resposta para "foi esse o motivo?" é:

- Sim, a falta de espaço foi um motivo real e comprovado;
- Não, não foi o único motivo dos gaps.

Causa final: combinação de ENOSPC + indisponibilidade operacional em janela histórica + bloqueio de SELL por guardrail + falhas 503 no endpoint de IA.

## Ações Recomendadas (Foco Agent)

1. Verificar health contínuo do endpoint de IA `:11437` e reduzir incidência de 503.
2. Revisar parâmetros de guardrail de SELL para evitar bloqueio excessivo em mercado de baixa.
3. Auditar reconciliação/saída de posições USDT-BRL (BUY sem SELL).
4. Adicionar alerta de "service sem logs" por janela maior que X minutos.
5. Adicionar métrica explícita de fallback rate de IA por profile.

## Status
Relatório concluído com base em evidências de logs de serviço e consultas ao banco de trades.
