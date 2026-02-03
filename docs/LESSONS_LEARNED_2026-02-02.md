# Lições aprendidas — 2026-02-02

## Contexto
- Painéis de monitoramento de conversas no Grafana não renderizavam dados.
- Pipeline de deploy para dev/cert/prod precisava de automação e segredo centralizado.

## Causas-raiz identificadas
1. **Grafana ↔ PostgreSQL sem rede Docker**
   - Datasource configurado com `localhost:5432` dentro do container, impedindo acesso ao Postgres.
2. **Validação de UI frágil**
   - Seletores do Selenium não cobriam o DOM moderno do Grafana.
3. **Pipeline usando runner público**
   - GitHub-hosted runner não acessa IP privado `192.168.15.2`.
4. **Caminhos de deploy inexistentes**
   - `/home/homelab/agents_workspace/{dev,cer,prod}` não existia no servidor.
5. **Healthcheck sensível a tempo**
   - Serviço reiniciado ainda não estava pronto quando o healthcheck rodou.

## Correções aplicadas
- **Rede e datasource do Grafana**
  - URL do datasource ajustada para `eddie-postgres:5432` (hostname do container).
  - Garantido que Grafana e Postgres estejam na mesma rede Docker.
- **Selenium / validação de UI**
  - Seletores expandidos para detectar tabelas modernas (`[role="table"]`, `[data-testid*="table"]`).
  - Esperas explícitas adicionadas para elementos dinâmicos.
- **Deploy pipeline**
  - Workflow atualizado para **runner self-hosted**.
  - Script de deploy com retries no healthcheck.
- **Ambientes no servidor**
  - Criada estrutura `/home/homelab/agents_workspace/{dev,cer,prod}`.
  - Repositório clonado em cada ambiente.
- **Secrets**
  - Vault local simples configurado e secrets armazenados.
  - Secrets DEV/CER/PROD registrados no GitHub.

## Resultados
- Painéis do Grafana renderizando corretamente.
- Pipeline de deploy dev → cer → prod executado com sucesso.
- Validações automatizadas sem falsos negativos.

## Prevenções e recomendações
- **Infra/Docker**: sempre usar hostname de serviço (`eddie-postgres`) em vez de `localhost` dentro de containers.
- **Pipelines**: para rede privada, usar **runner self-hosted** ou túnel público controlado.
- **Healthcheck**: adotar retry/backoff em scripts de deploy.
- **Selenium**: manter fallback selectors para mudanças de DOM.
- **Secrets**: priorizar Bitwarden; manter fallback no `tools/simple_vault` com passphrase segura e backup.

## Referências
- [scripts/deploy_env.sh](../scripts/deploy_env.sh)
- [.github/workflows/deploy-dev-cer-prod.yml](../.github/workflows/deploy-dev-cer-prod.yml)
- [docs/SECRETS.md](SECRETS.md)
- [docs/VAULT_README.md](VAULT_README.md)
- [docs/DASHBOARD_FIX_LOG.md](DASHBOARD_FIX_LOG.md)
