# 🛡️ Taxonomy Enforcement

Como a taxonomia é **obrigatória** no fluxo multi-agente e multi-ferramenta.

---

## 1. Camadas

| Camada | Onde | Domínios | Bloqueia |
|--------|------|----------|----------|
| **PreToolUse** | Claude Code, Cursor, Grok | variables, tables, apis | `duplicate` → deny |
| **pre-commit** | `.githooks/pre-commit` | variables [10], tables [11], apis [12] | `duplicate` → exit 1 |
| **CI** | GitHub Actions em PRs `main` | 3 workflows | `duplicate` → job fail |

| Status | PreToolUse | pre-commit / CI |
|--------|------------|-----------------|
| `ok` | silêncio | silêncio |
| `duplicate` | **deny** | **fail** |
| `lint` | warn | warn (não falha) |
| `new` | warn | warn (não falha) |

Codex CLI: sem PreToolUse nativo; cobertura garantida = pre-commit + CI.

---

## 2. Hooks PreToolUse

Arquivos (espelhados):

- `hooks.json`
- `.claude/settings.json`
- `.cursor/hooks.json`
- `.grok/hooks/claude-code-import.json`

Comandos (nesta ordem, após guardrails gerais):

```text
tools/hooks/variable_registry_validate.py
tools/hooks/table_registry_validate.py
tools/hooks/api_registry_validate.py
```

Cada um:

1. Lê stdin JSON do hook (`tool_input.command|new_string|content|file_path`)
2. Extrai candidatos (vars / CREATE TABLE / decorators)
3. Classifica contra o catálogo do domínio
4. Emite JSON de decisão (`permissionDecision: deny` ou `additionalContext` warn)

---

## 3. Pre-commit

Repo usa `core.hooksPath=.githooks` (sem install extra).

Trecho relevante:

```bash
# [10/12] variables
python3 tools/hooks/variable_registry_validate.py --staged

# [11/12] tables
python3 tools/hooks/table_registry_validate.py --staged

# [12/12] apis
python3 tools/hooks/api_registry_validate.py --staged
```

`--staged` analisa **apenas linhas adicionadas** (`git diff --cached -U0`), reduzindo ruído.

Verificar:

```bash
git config core.hooksPath
# esperado: .githooks
```

---

## 4. CI workflows

| Workflow | Script |
|----------|--------|
| `.github/workflows/variable-registry-check.yml` | `variable_registry_validate.py` nos files do PR |
| `.github/workflows/table-registry-check.yml` | `table_registry_validate.py` |
| `.github/workflows/api-registry-check.yml` | `api_registry_validate.py` |

Diff: `base.sha` … `head.sha`, filter ACM.

---

## 5. Regras de classificação por domínio

### Variables (`variable_registry_validate.py`)

| Caso | Status |
|------|--------|
| Nome exato no catálogo | ok |
| Normalização igual (remove `_-.`, upper) | **duplicate** |
| Fuzzy ≥ 0.86 | **duplicate** (possível typo) |
| Fora de `UPPER_SNAKE_CASE` | lint |
| Novo genuíno | new |

### Tables (`table_registry_validate.py`)

| Caso | Status |
|------|--------|
| FQN ou bare name no catálogo | ok |
| Fuzzy ≥ 0.88 | **duplicate** |
| Fora de `snake_case` / `schema.table` | lint |
| Nova | new |

Extrai de: `CREATE TABLE [IF NOT EXISTS] [schema.]name` (+ resolve `{SCHEMA}`).

### APIs (`api_registry_validate.py`)

| Caso | Status |
|------|--------|
| `METHOD /path` exato | ok |
| Fuzzy mesmo método ≥ 0.90 | **duplicate** |
| Path sem `/` | lint |
| Novo | new |

Extrai de: `@app.get("/x")`, `@router.post`, Flask `route`, OpenAPI path+method.

Normalização de path: `{id:path}` → `{id}`, trailing slash removida.

---

## 6. O que NÃO é bloqueado

- Criar nome **genuinamente novo** (só warn → documentar + rescanear)
- Table `unused` ou API `orphan` (métrica/report, não gate)
- Lint de snake_case / UPPER_SNAKE (warn)
- Edição de arquivos sem padrões de var/table/route

---

## 7. Mensagens típicas

### Duplicate (bloqueia)

```text
'POST /orderr' é muito parecida com 'POST /order' (categoria 'trading').
Confirme se não é o mesmo contrato antes de criar outro.
```

```text
'btc.tradez' é muito parecida com 'btc.trades' ...
```

```text
'APITOKEN' é uma variação de 'API_TOKEN' ...
```

### New (warn)

```text
'COMPLETELY_NEW_ENDPOINT' não está no catálogo (.apis-catalog/catalog.json).
Documente em docs/taxonomy/APIS.md e rode python3 tools/catalog_apis.py ...
```

---

## 8. Bypass (emergência)

```bash
git commit --no-verify   # pula pre-commit inteiro
```

**Não use** em rotina. CI ainda valida no PR.

---

## 9. Checklist de implementação de gate novo

1. Scanner → `catalog.json`
2. Hook `tools/hooks/<domain>_registry_validate.py` (modos hook + CLI)
3. Wire PreToolUse nos 4 arquivos de hooks
4. Check em `.githooks/pre-commit`
5. Workflow `.github/workflows/<domain>-registry-check.yml`
6. Testes unitários de extract/classify
7. Docs (este arquivo + README do domínio)

---

## 10. Manutenção

| Ação | Comando |
|------|---------|
| Validar staged agora | `python3 tools/hooks/*_registry_validate.py --staged` |
| Atualizar fonte de verdade | `python3 tools/catalog_taxonomy.py --domain …` |
| Rodar testes de gate | `pytest tests/test_*_registry_validate.py` |
