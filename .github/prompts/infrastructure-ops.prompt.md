---
description: "Use when: planning or executing infrastructure operations for homelab, docker, systemd, ssh, and deploy safety"
---

# Infrastructure Ops Prompt

## Objetivo
Executar operacoes de infraestrutura com seguranca, previsibilidade e verificacao.

## Entrada esperada
- Ambiente alvo.
- Servicos afetados.
- Restricoes operacionais.

## Saida esperada
- Sequencia de comandos segura.
- Checkpoints de validacao por etapa.
- Plano de rollback quando aplicavel.

## Regras
- Confirmar impacto em servicos criticos.
- Validar estado apos cada comando.
- Evitar mudancas irreversiveis sem checkpoint.
