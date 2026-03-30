---
name: homelab-deployment
description: "Use when: deploying services to homelab, editing docker or systemd configs, and validating server-side rollout safety"
---

# Homelab Deployment

## Objetivo
Executar mudancas de deploy e infraestrutura com checkpoints de seguranca e rollback claro.

## Quando usar
- Ajustes em Docker, systemd, ssh e deploy.
- Validacao de rollout em homelab.
- Mudancas em servicos locais ou remotos do stack principal.

## Workflow
1. Identificar ambiente e servicos afetados.
2. Verificar se ha servico critico que exige confirmacao.
3. Aplicar mudanca com validacao por etapa.
4. Rodar healthcheck e registrar rollback.

## Regras obrigatorias
- Nao reiniciar servicos criticos sem checkpoint.
- Validar comando anterior antes do proximo.
- Explicitar rollback quando houver restart ou deploy.

## Validacao
- Status do servico.
- Logs recentes.
- Endpoint ou healthcheck funcional.

## Exemplo
Pedido: "ajuste unit systemd do specialized-agents-api e valide subida".
