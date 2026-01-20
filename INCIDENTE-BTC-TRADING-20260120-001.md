# INCIDENTE: BTC Trading API Offline

**Data/Hora:** 20 de janeiro de 2026
**Responsável:** OperationsAgent

---

## Descrição do Incidente
O serviço **BTC Trading API** (porta 8510) encontra-se **offline/inacessível**.

## Detalhes do Diagnóstico
- Endpoint testado via `curl` está inacessível (timeout ou conexão recusada).
- Indício de que o serviço pode estar parado ou travado.
- Não há resposta na porta 8510.

## Impacto Potencial
- **AutoCoinBot** impossibilitado de executar operações de trading de Bitcoin.
- Risco de perdas financeiras por impossibilidade de negociação automática.
- Interrupção de fluxos dependentes do BTC Trading API.

## Ação Solicitada
- **Investigação imediata** da causa raiz da indisponibilidade.
- **Restauração urgente** do serviço BTC Trading API.
- Atualizar este ticket com diagnóstico detalhado e plano de ação.

---

**Protocolo:** INCIDENTE-BTC-TRADING-20260120-001

---

Favor priorizar este incidente devido ao impacto direto em operações críticas de trading.
