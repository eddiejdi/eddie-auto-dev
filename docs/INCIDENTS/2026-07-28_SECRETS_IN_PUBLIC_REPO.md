# Credenciais em claro no repositório público — 2026-07-28

## Resumo

`eddiejdi/eddie-auto-dev` é **público desde 2026-01-09**. Uma varredura por
padrões de credencial nos arquivos rastreados encontrou segredos em claro, dois
deles **ainda válidos** no momento da descoberta.

Descoberto ao revisar o que entraria num commit não relacionado (seletor de
servidor ProtonVPN).

## Falso positivo descartado antes

A primeira suspeita foi `.variables-catalog/catalog.json`, que guarda um campo
`value` por variável. **Não é vazamento:** `tools/catalog_variables.py:92`
já redige via `_is_sensitive()`, e todas as entradas sensíveis contêm
literalmente `***REDACTED***` — inclusive no commit mais antigo (2026-06-21).
O erro veio de um filtro que tratava qualquer valor com mais de 8 caracteres
como segredo; a máscara tem 14.

## Credenciais ativas no momento da descoberta

| Arquivo | Credencial | Exposto desde | Verificação |
|---|---|---|---|
| `tools/systemd/specialized-agents-api-ha.conf` | Token long-lived do Home Assistant | 2026-02-23 | `HTTP 200` na API do HA |
| `tools/wiki_bulk_publish.py` | JWT da API do Wiki.js, claim `grp:1` (admin) | 2026-06-18 | `exp` 2027-03-15, assinatura válida |

O token do HA dá controle da automação residencial inteira. O do Wiki.js é de
grupo administrador.

## Credenciais já revogadas

Cinco arquivos continham bot tokens do Telegram que **já não autenticam**
(`getMe` → `Unauthorized`). Continuavam sendo credenciais publicadas:

- `.mcp.json` (2026-04-25)
- `monitoring/grafana/provisioning/alerting/contactpoints.yml` (2026-03-04)
- `tools/telegram_mcp_server.py` (2026-04-25)
- `scripts/misc/linkedin_job_scanner.py` (2026-03-07)
- `tools/ollama-gpu-selfheal.service` (2026-05-17)

`docs/GITHUB_RUNNER_SETUP.md` contém `ghp_xxxxxxxxxx` — placeholder, não é
credencial.

## Correções aplicadas

Todas removem o valor do repositório; **nenhuma rotaciona credencial** (isso
exige ação do dono da conta).

| Arquivo | Como passou a resolver |
|---|---|
| `tools/wiki_bulk_publish.py` | `secrets_loader.get_field('wikijs/api_key', 'password')`, lazy e com fallback para `WIKI_TOKEN` do ambiente |
| `tools/systemd/specialized-agents-api-ha.conf` | `EnvironmentFile=-/etc/eddie/home-assistant.env`, gerado fora do git por `install_tray_always_on.sh` a partir de `eddie/home_assistant_token` |
| `.mcp.json` | Comando SSH passou a carregar `/etc/default/eddie-common` e mapear `TELEGRAM_BOT_TOKEN` → `TG_TOKEN` |
| `tools/telegram_mcp_server.py` | Sem default embutido; aceita `TG_TOKEN` ou `TELEGRAM_BOT_TOKEN`, e falha com mensagem clara se ausente |
| `scripts/misc/linkedin_job_scanner.py` | Sem default embutido |
| `tools/ollama-gpu-selfheal.service` | `EnvironmentFile=-/etc/default/eddie-common` |
| `monitoring/grafana/provisioning/alerting/contactpoints.yml` | `bottoken: "$TELEGRAM_BOT_TOKEN"` |

### Armadilha encontrada na correção

`/etc/default/eddie-common` define `TELEGRAM_BOT_TOKEN`, mas o servidor MCP lê
`TG_TOKEN`. A primeira versão da correção do `.mcp.json` teria quebrado o MCP do
Telegram silenciosamente. O mapeamento explícito resolve, e o servidor passou a
aceitar os dois nomes.

## Pendências

1. **Rotacionar as duas credenciais ativas** — HA (Perfil → Tokens de acesso) e
   Wiki.js (Admin → API). Enquanto não forem revogadas, seguem válidas para
   qualquer pessoa que tenha clonado o repo, mesmo com o código já limpo.
2. **`TELEGRAM_BOT_TOKEN` no container do Grafana** — hoje ele não tem a
   variável, então o contact point do Telegram não entrega. Já estava quebrado
   antes desta mudança, porque o token no arquivo estava revogado.
3. **Senha do Postgres (`eddie_memory_2026`) em 29 arquivos rastreados** —
   incluindo `.mcp.json`, `monitoring/grafana/provisioning/datasources/datasources.yml`,
   exporters e docs. Não coberto por esta correção: a varredura inicial usava
   padrões de token e não pega senha simples. Escopo separado.
4. **Histórico do git** — os valores seguem acessíveis em commits antigos e em
   qualquer clone. Limpar exige reescrita de histórico e force-push num repo
   público, quebrando clones existentes. Com as credenciais rotacionadas, passa
   a ser opcional.
