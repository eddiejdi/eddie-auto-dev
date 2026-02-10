# DEPLOY LOG — Bus Debug (06/02/2026)

Resumo das ações realizadas para implementar e disponibilizar o _Bus Debug_ no painel **Saída**.

---

## Objetivo
- Exibir, em tempo real, as mensagens do `AgentCommunicationBus` no painel de Saída quando o usuário executa um prompt de IA.

## Alterações principais

- Backend: `specialized_agents/api.py`
  - `/code/generate-stream` passou a publicar eventos do bus como SSE inline com prefixo `[BUS]` (JSON).
  - Adicionado endpoint SSE: `GET /bus/stream` para monitoramento do bus em tempo real.

- Frontend: `site/ide.js`
  - `generateCodeWithAIStream()` aceita callback `onBus` e parseia mensagens `[BUS]` do stream.
  - Funções novas: `formatBusMessage()`, `appendBusToOutput()` para formatar e exibir debug com ícones.
  - `handleAIPromptRun()` atualizado para resetar e exibir as mensagens do bus nos modos `code`, `ask` e `agents`.

- Infra / Nginx
  - Adicionado proxy reverse `location /agents-api/` → `http://127.0.0.1:8503/` (SSE + CORS) para evitar mixed-content e falhas DNS (`api.rpa4all.com` não resolvia).
  - Cache-bust em `index.html` para evitar servir JS antigo (`ide.js?v=...`).

- Teste automatizado
  - Adicionado `test_bus_debug_selenium.py` (Selenium) para validar visualização do Bus Debug nos 3 modos.

## Commits e artefatos

- Commit principal: `ff4f74d` (muda frontend + backend + testes)
- Arquivos alterados / adicionados:
  - `specialized_agents/api.py` (modificado)
  - `site/ide.js` (modificado)
  - `site/index.html` (cache-bust)
  - `test_bus_debug_selenium.py` (novo)

## Comandos executados (registro)

- Deploy de arquivos para servidor (exemplos executados):
```bash
scp site/ide.js homelab@192.168.15.2:/var/www/rpa4all.com/ide.js
scp specialized_agents/api.py homelab@192.168.15.2:/home/homelab/eddie-auto-dev/specialized_agents/api.py
- Reiniciar serviço da API no homelab:
```bash
ssh homelab@192.168.15.2 'sudo systemctl restart specialized-agents-api && sudo systemctl is-active specialized-agents-api'
- Limpar cache e reload Nginx:
```bash
ssh homelab@192.168.15.2 'sudo rm -rf /var/cache/nginx/* && sudo systemctl reload nginx'
- Criar proxy Nginx para `/agents-api/` (inserido na configuração `www.rpa4all.com`) e recarregar Nginx:
```bash
# (edits via sed/cat feitos durante a ação)
sudo nginx -t && sudo systemctl reload nginx
- Trigger do GitHub Actions (Deploy to Homelab):
```bash
gh workflow run --repo eddiejdi/eddie-auto-dev "Deploy to Homelab" --ref main
gh run list --repo eddiejdi/eddie-auto-dev --workflow=deploy-to-homelab.yml --limit 5
gh run watch <run-id> --repo eddiejdi/eddie-auto-dev
## Resultado

- Workflow `Deploy to Homelab` (run id 21752986038) executado com `success`.
- Teste Selenium (`test_bus_debug_selenium.py`) executado localmente: passou — confirmou que o Bus Debug aparece nos modos `code`, `ask` e `agents` e que mensagens esperadas (`TASK_START`, `LLM_CALL`, `LLM_RESPONSE`, `CODE_GEN`, `TASK_END`) foram exibidas.

## Verificações manuais

- Teste do endpoint streaming (via CLI) — retorno exemplo:
```text
data: [BUS] {"type": "task_start", "source": "api", "target": "system", ...}
data: ```
data: python
data: print(...)
- Teste via proxy HTTPS (Nginx):
```bash
curl -sN -X POST https://www.rpa4all.com/agents-api/code/generate-stream \
  -H 'Content-Type: application/json' \
  -d '{"language":"python","description":"hello world","context":""}' | head -20
## Logs importantes

- Workflow run id: `21752986038` — status: `success` (verificado via `gh run list` e `gh run watch`).

## Possíveis melhorias / próximos passos

- Adicionar filtros na UI para tipos de mensagem do bus (ON/OFF por tipo).
- Persistir logs do bus em arquivo/DB para auditoria e correlação (opcional já suportado por `AgentCommunicationBus.export_messages`).
- Adicionar toggle granular para ativar/desativar debug do bus por usuário/sessão.

## Rollback (se necessário)

- Reverter commit `ff4f74d` e reiniciar a API + recarregar Nginx:
```bash
git revert ff4f74d
git push origin main
# Reiniciar API e reload nginx no homelab
ssh homelab@192.168.15.2 'sudo systemctl restart specialized-agents-api && sudo systemctl reload nginx'
---

Arquivo criado automaticamente pelo assistente em: 2026-02-06
