---
name: security-hardening
description: "Use when: auditing secrets exposure, hardening CI/CD, reviewing risky commands, and enforcing safe operational guardrails"
---

# Security Hardening

## Objetivo
Reduzir risco operacional e de vazamento de credenciais em codigo e automacoes.

## Quando usar
- Revisao de seguranca em scripts e workflows.
- Mudancas com comandos destrutivos ou privilegios elevados.
- Checagem de segredos em configuracoes e logs.

## Workflow
1. Identificar superficie de risco (segredos, comandos, rede, permissao).
2. Classificar impacto e probabilidade.
3. Aplicar mitigacoes de menor risco operacional.
4. Validar controles com checklist objetivo.

## Regras obrigatorias
- Nunca expor token/senha em logs.
- Evitar comandos destrutivos sem aprovacao.
- Preferir cofres/variaveis de ambiente para credenciais.
- Revisar workflows para reduzir permissao e escopo.

## Validacao
- Verificar se segredos nao aparecem em arquivos versionados.
- Verificar se comandos criticos possuem protecao procedural.
- Confirmar trilha de auditoria minima.

## Falhas comuns
- Hardcode de credencial em script.
- Fluxo CI com permissao ampla desnecessaria.
- Restart de servico critico sem checkpoint.

## Exemplo de uso
Pedido: "revise workflow de deploy para reduzir risco".
Saida esperada: ajustes de seguranca com justificativa e impacto esperado.
