---
description: "Use when: editing orchestration, automation, deployment, exporter, workflow, agent, or operational flow files where preserving the existing execution sequence is critical"
applyTo: "specialized_agents/**,grafana/exporters/**,tools/**,scripts/**,deploy/**,systemd/**,.github/agents/**,.github/prompts/**,.github/instructions/**,docs/**/*flow*.md,docs/**/*workflow*.md"
---

# Regras Anti-Alteracao de Fluxo

## Objetivo
- Preservar o fluxo operacional existente.
- Bloquear refactors automáticos que mudem ordem, semântica ou contratos entre etapas.

## Regra central
- Se o pedido nao exigir explicitamente mudar o fluxo, o agente deve manter a sequencia atual de execucao, os mesmos checkpoints, os mesmos side effects e os mesmos contratos de entrada/saida.

## O que o agente NAO pode fazer por conta propria
- Reordenar etapas de orquestracao ou automacao.
- Substituir um fluxo multi-step por uma versao "simplificada".
- Mudar condicoes de fallback, retry, cooldown, polling, locks ou rate limits sem necessidade comprovada.
- Alterar nomes de servicos, containers, env vars, timers, units systemd, jobs, rotas, comandos operacionais ou formatos de payload usados por outros componentes.
- Trocar uma fonte de verdade operacional por outra sem confirmar compatibilidade com o fluxo existente.
- Remover validacoes, auditoria, logs, checkpoints ou rollback implicitos no fluxo atual.

## O que o agente deve fazer por padrao
- Preferir patches minimos e localizados.
- Corrigir a causa raiz sem redesenhar a arquitetura do fluxo.
- Manter compatibilidade retroativa com scripts, services e automacoes ja existentes.
- Ao tocar fluxo critico, explicitar mentalmente: estado atual, causa da mudanca, impacto esperado e rollback.
- Preservar nomes, portas, arquivos, binds, sequencias de start/stop e dependencias cruzadas, salvo instrucao explicita em contrario.

## Mudancas permitidas sem escalar
- Ajuste pontual de bug mantendo a mesma sequencia do fluxo.
- Inclusao de guardrail, validacao adicional ou observabilidade que nao altere o comportamento nominal.
- Correcao de endereco, path, flag ou parametro quando isso restaura o fluxo definido.

## Mudancas que exigem cautela maxima
- Arquivos de exporter/self-heal, automacoes de deploy, scripts de recovery, services systemd, agentes de orquestracao e qualquer codigo que reinicie servicos ou recrie containers.
- Fluxos com persistencia, reputacao, ganhos financeiros, mensageria entre agentes ou integracoes de infraestrutura.

## Regra de documentacao
- Quando o pedido for "documentar" ou "aplicar markdown", adicione protecoes instrucionais sem reescrever o fluxo em si.

## Frase operacional obrigatoria
- "Preserve o fluxo existente; altere apenas o minimo necessario para restaurar ou proteger o comportamento atual."