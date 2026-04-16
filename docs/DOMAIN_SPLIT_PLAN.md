# Domain Split Plan

## Objetivo
Separar o monorepo atual em tres repositorios com responsabilidade clara:

- `eddiejdi/eddie-trading`
- `eddiejdi/eddie-homelab`
- `eddiejdi/eddie-shared`

## Regra de dominio
- `trading`: tudo que executa estrategia, ingestao de mercado, sentimento, deploy/runtime de trading e observabilidade especifica de trading.
- `homelab`: tudo que opera o host, rede, Docker, Cloudflare, VPN, runners e automacao de infraestrutura.
- `shared`: tudo que e contrato reutilizavel entre dominios.

## Repositorio Trading
Entram aqui:

- `btc_trading_agent/`
- `clear_trading_agent/`
- `grafana/exporters/rss_sentiment_exporter.py`
- `grafana/exporters/rss_llm_trainer.py`
- `scripts/deploy_btc_trading_profiles.sh`
- `scripts/candle_collector.py`
- `scripts/ollama_finetune_batch.py`
- `systemd/crypto-agent@.service`
- `systemd/rss-sentiment-exporter.service`
- `systemd/candle-collector.service`
- `systemd/ollama-finetune.service`

Nao devem ficar aqui:

- runbooks e workflows genericos de homelab
- scripts de VPN, Cloudflare, runner e recovery do host
- contratos compartilhados que sirvam mais de um dominio

## Repositorio Homelab
Entram aqui:

- `deploy/`
- `docker/`
- `tools/homelab/`
- `tools/homelab_recovery/`
- `vpn/`
- workflows de infra e deploy de host
- docs de servidor, recovery, Cloudflare e rede

Nao devem ficar aqui:

- codigo de estrategia ou runtime do trading
- exporters e modelos que existam apenas para trading

## Repositorio Shared
Entram aqui:

- SDK/cliente do `secrets_agent`
- contratos do Authentik
- hooks/copilot guardrails reutilizaveis
- libs de automacao reaproveitadas por mais de um dominio

Regra importante:

- `shared` nao carrega deploy de host
- `shared` nao carrega logica de trading
- `shared` fornece contratos versionados consumidos por `trading` e `homelab`

## Fase 1
Separacao logica dentro do monorepo:

- definir ownership por dominio
- bloquear novos vazamentos com validacao automatica
- tirar paths absolutos antigos de `trading`
- reduzir dependencias de `trading` em `/home/homelab/...`

## Fase 2
Extracao fisica:

- criar repos `eddie-trading`, `eddie-homelab`, `eddie-shared`
- mover diretorios por dominio preservando historico com `git filter-repo` ou `git subtree split`
- publicar `shared` como dependencia externa versionada

## Fase 3
Consumo externo de shared

- `trading` consome `shared` por tag/version
- `homelab` consome `shared` por tag/version
- remover copias locais duplicadas e referencias cruzadas por path

## Guardrail atual
O arquivo [config/domain_boundaries.json](/workspace/eddie-auto-dev/config/domain_boundaries.json) define o ownership inicial.

O script [validate_domain_boundaries.py](/workspace/eddie-auto-dev/scripts/validate_domain_boundaries.py) faz a validacao inicial do escopo monitorado:

```bash
python3 scripts/validate_domain_boundaries.py
python3 scripts/validate_domain_boundaries.py --strict
```
