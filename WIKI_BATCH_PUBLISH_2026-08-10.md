# Operação 2026-08-10 — Publicação em lote dos `.md` na Wiki RPA4All

## Resumo

Publicação de **707 arquivos Markdown** do repositório `eddie-auto-dev` na Wiki
RPA4All via agente **`wiki_rpa4all`**, com intervalo de **30s** entre publicações para
preservar o homelab de picos de carga.

- **Ferramenta:** `tools/loop_publish_markdown_to_wiki_agent.py`
- **Endpoint:** `POST /wiki/publish` no WikiAgent (`http://192.168.15.2:8503`)
- **Modelo de expansão:** `phi4-mini:latest` no **NAS** (`192.168.15.4:11546`, free)
- **Locale:** `pt` · **Tags:** `auto-sync`, `markdown`, `<pasta-topo>`
- **Duração estimada:** ~11-12h (~1 arquivo/min: geração Ollama + 30s de sleep)

> Pré-requisito resolvido nesta sessão: caminho cloud do router estava quebrado
> (401). Ver `docs/INCIDENTS/2026-08-10_WIKI_PUBLISH_OPENROUTER_401_NAS_PHI4.md`.

---

## Comando executado

```bash
# Workstation (workdir: /workspace/eddie-auto-dev)
setsid -f .venv/bin/python tools/loop_publish_markdown_to_wiki_agent.py \
  --agent-url http://192.168.15.2:8503 \
  --sleep-seconds 30 \
  --once \
  > /tmp/opencode/wiki_publish.log 2>&1 < /dev/null
```

- `setsid -f` — desacopla totalmente do terminal (roda em background, sobrevive ao fim da sessão).
- `--once` — um ciclo completo (707 arquivos) e encerra.
- PID do processo: **1346660**.

## Escopo dos arquivos

Lista gerada por `rg --files -g "*.md"` (respeita `.gitignore`), em ordem estável:

| Origem | Qtde |
|--------|------|
| `docs/` | 570 |
| raiz `*.md` | 62 |
| `tools/` | 19 |
| `assets/copilot/` | 11 |
| `solutions/` | 10 |
| `deploy/` | 10 |
| `android/`, `site/`, `scripts/`, `ops/`, `knowledge_base/`, `grafana/`, `artifacts/`, `systemd/`, `marketing/`, `content_automation/`, `blueprism/` | 1-5 cada |

Excluídos automaticamente (gitignored): `.venv*`, `.claude/worktrees`, `.github/`,
`.tmp/`, catálogos gerados (`.taxonomy-catalog`, `.variables-catalog`, etc.),
`.pytest_cache/`.

## Mapeamento de paths (wiki)

Reusa a heurística de `tools/hooks/wiki_sync.py` → `infer_path()`:

- Prefixos de domínio (ex: `TRADING_` → `trading/`, `LTFS_` → `homelab/storage/ltfs/`,
  `GRAFANA_` → `homelab/monitoring/`, `DEPLOYMENT_` → `operations/deploy/`)
- Sem prefixo → `docs/<slug>` (raiz) ou `docs/<pasta>/<slug>`
- Upsert: páginas existentes são **atualizadas**, novas são **criadas**

## Comportamento e carga

- **Carga no servidor:** geração no NAS (não usa GPU0/trading); Wiki.js processa um
  create/update por vez a cada ~45-60s. Intervalo de 30s evita sobrecarga de render.
- **Falhas por arquivo:** o script loga o erro e continua (`ERRO HTTP ...` / `ERRO em ...`).

## Monitoramento

```bash
# Progresso real (contagem de publishes 200 OK) — log do script tem buffering:
ssh homelab 'sudo journalctl -u specialized-agents-api --since "..." --no-pager | grep -c "POST /wiki/publish HTTP/1.1\" 200"'

# Log do loop (pode aparecer vazio até o buffer do Python liberar):
tail -f /tmp/opencode/wiki_publish.log

# Verificar página específica na wiki:
ssh homelab 'TOKEN=$(sudo systemctl show specialized-agents-api -p Environment | tr " " "\n" | grep "^WIKI_TOKEN=" | cut -d= -f2); \
  curl -s -X POST http://127.0.0.1:3009/graphql -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '\''{"query":"{ pages { singleByPath(path: \"docs/agents\", locale: \"pt\") { id path title } } }"}'\'''
```

## Resultados parciais (início do lote)

| Arquivo | Wiki path | Status |
|---------|-----------|--------|
| `AGENTS.md` | `docs/agents` | ✅ criado (id 682) |
| `CLAUDE_CODE_PROXY_FIX_2026-04-26.md` | `docs/claude-code-proxy-fix` | ✅ atualizado (id 116) |
| `CLOSED_OPEN_POSITIONS_SUMMARY.md` | `docs/closed-open-positions-summary` | ✅ atualizado (id 117) |

## Pendências

- **Páginas smoke a deletar** (requer confirmação do dono — contrato do agente exige
  aprovação explícita para delete):
  - `operations/wiki-smoke-inventory` (page id 731)
  - `operations/wiki-smoke-nas-ollama` (page id 732)

## Referências

- Agente: `.github/agents/wiki_rpa4all.agent.md`
- Fix do router: `docs/INCIDENTS/2026-08-10_WIKI_PUBLISH_OPENROUTER_401_NAS_PHI4.md`
- Script: `tools/loop_publish_markdown_to_wiki_agent.py`
- Heurística de path: `tools/hooks/wiki_sync.py`
