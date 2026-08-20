# Anti-Regression & Deploy Safety — Homelab RPA4All

**Data:** 2026-08-20  
**Status:** Ativo  
**Aplica-se a:** eddie-auto-dev, homelab (192.168.15.2), NAS (RTX 2060)

## Visão Geral

Este documento consolida as práticas, hooks, workflows e políticas que evitam
regressão de código funcional e asseguram deploys efetivos no homelab. As
barreiras estão distribuídas em 4 camadas: local (dev), commit, push, e CI/CD.

```
┌─────────────────────────────────────────────────────────────────┐
│ CAMADA 1: LOCAL (dev machine)                                   │
│  • pre-commit: 15 checks (token scan, lint, py_compile, CMDB…)  │
│  • ruff check nos arquivos staged                              │
│  • py_compile (sintaxe válida)                                  │
├─────────────────────────────────────────────────────────────────┤
│ CAMADA 2: PUSH (antes de sair da máquina)                       │
│  • pre-push: ruff + pytest smoke (8 testes críticos de trading) │
│  • Bloqueia push para main/master/prod/production               │
│  • Bypass: ALLOW_PUSH=1 ou --no-verify (emergências)            │
├─────────────────────────────────────────────────────────────────┤
│ CAMADA 3: CI (GitHub Actions, em PR para main)                   │
│  • regression-gate.yml: ruff + py_compile + pytest unit + hooks  │
│  • python-ci.yml: testes BTC + Clear Agent (self-hosted runner) │
│  • Status checks obrigatórios (ver Branch Protection abaixo)    │
├─────────────────────────────────────────────────────────────────┤
│ CAMADA 4: DEPLOY (ci.yml, em push para main)                     │
│  • Health-check pós-deploy (systemd, portas, APIs)              │
│  • Rollback automático se health-check falhar                   │
│  • Notificação Telegram (sucesso, falha, rollback)             │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Branch Protection (GitHub)

Configurar no repositório `eddiejdi/eddie-auto-dev`:

### Regras para `main`
| Setting | Valor | Razão |
|---------|-------|-------|
| Require PR before merging | ✅ | Ninguém mergeia direto em main |
| Required status checks | ✅ | `Ruff Lint`, `Pytest Unit (regression gate)`, `Python Tests` |
| Require branches up-to-date | ✅ | PR deve estar rebaseado com main |
| Required approvals | 1+ | Code review obrigatório |
| Dismiss stale approvals on push | ✅ | Novo push invalida aprovações |
| Restrict force pushes | ✅ | Política nº 4 do AGENTS.md |
| Restrict deletions | ✅ | main não pode ser deletada |
| Linear history | ✅ | Rebase/merge clean |
| CODEOWNERS para `systemd/` | ✅ | Mudanças em produção exigem revisor extra |

### Regras para `systemd/` (path rule)
- Required reviewers: `edenilson-adm` + 1 reviewer adicional
- Não permite push direto — só via PR

## 2. Hooks Git Ativos

### `.githooks/pre-commit` (15 checks)
1. Token scan (sk-ant, sk-proj, ghp_, glpat, 40+ hex)
2. .env file restrictions (só .env.consolidated, .env.example* OK)
3. GPU-first config check (OLLAMA_HOST)
4. Test coverage check (avisa se btc_trading_agent/ sem testes)
5. GPU-first validator (10s timeout)
6. OLLAMA_HOST coordinator port (bloqueia :11434/:11435 direto)
7. Grafana dashboard UID uniqueness
8. Incomplete markers (stubs, NotImplementedError, # stub-ok escape)
9. CMDB baseline + trading overrides (regenera no mesmo commit)
10. Variable taxonomy (duplicatas)
11. Table taxonomy (duplicatas)
12. API taxonomy (duplicatas)
13. Wiki documentation analyzer
14. **ruff check** (arquivos Python staged — novo 2026-08-20)
15. **py_compile** (sintaxe válida — novo 2026-08-20)

### `.githooks/pre-push` (novo 2026-08-20)
- Detecta push para branches protegidas: `main`, `master`, `prod`, `production`
- Roda `ruff check` (se disponível) nos diretórios críticos
- Roda `pytest` smoke (8 testes críticos de trading, <60s)
- **Bypass:** `ALLOW_PUSH=1 git push ...` ou `git push --no-verify ...`

### `.githooks/post-commit`
- Memory ingest (git → Chroma)
- Wiki sync (publicação automática de .md)

### Ativar hooks (1x por clone)
```bash
make setup-hooks
# ou manualmente:
git config core.hooksPath .githooks
chmod +x .githooks/*
```

## 3. CI Workflows

### `regression-gate.yml` (novo 2026-08-20)
- **Trigger:** PR para main (opened, synchronize, reopened)
- **Runner:** self-hosted homelab
- **Jobs:**
  1. `ruff-lint` — ruff check nos diretórios críticos
  2. `py-compile` — sintaxe em todos os .py do repo
  3. `pytest-unit` — suíte completa (excluindo integration/external)
  4. `pre-commit-hooks` — hooks de domínio (incomplete markers, taxonomias)
  5. `regression-gate-summary` — consolidado (falha se qualquer job falhar)
- **Artifact:** log de pytest retido 14 dias

### `python-ci.yml` (existente)
- **Trigger:** PR para main
- **Runner:** self-hosted homelab
- **Jobs:**
  1. `python-tests` — 11 testes críticos do BTC trading agent
  2. `clear-agent-tests` — testes do Clear Trading Agent (B3)

### `ci.yml` (existente, atualizado 2026-08-20)
- **Trigger:** push para main
- **Jobs:**
  1. `unit-tests` — subconjunto de testes (ubuntu-latest)
  2. `check` — verificação de sintaxe Python + YAML
  3. `deploy` — deploy via SSH + **health-check pós-deploy** (novo)
     - Se health-check falhar → **rollback automático** (git reset --hard HEAD~1)
     - Notifica Telegram: sucesso ✅, falha ❌, rollback ⏪

## 4. Health Check Pós-Deploy

`scripts/health-check-post-deploy.sh` verifica:

1. **SSH** para homelab (conectividade)
2. **systemd services:**
   - clear-trading-agent
   - crypto-agent@BTC_USDT_aggressive
   - crypto-agent@BTC_USDT_conservative
   - specialized-agents
   - ollama.service
3. **Portas críticas:**
   - 127.0.0.1:5433 (Postgres schema btc)
   - 127.0.0.1:8503 (Communication Bus MCP)
4. **HTTP endpoints** (configurável via `CRITICAL_HTTP`)

Se qualquer item falhar → exit 1 → CI aplica rollback automático.

## 5. Governance Layer (MCP)

O homelab já tem o Governance Layer (`intent_declare`) que exige aprovação
humana via Telegram para:
- Ações com `risk_level >= medium`
- Deploys e restarts (forçados para medium mesmo se declarados low)
- Trava de deploy 2026-08-09: `action_type='deploy'` ou `'restart'` sempre
  exigem aprovação

Fluxo:
```
intent_declare(risk_level='medium') → intent_id
↓
intent_check_status(intent_id) → aguarda "approved" via Telegram
↓
[executa ação] → intent_complete(intent_id, success=True/False)
```

## 6. Deploy do NAS (RTX 2060)

O NAS hospeda o modelo `trading-analyst:latest` (decisão 2026-08-12).
Procedimento de deploy seguro:

1. **Antes de atualizar o modelo:**
   ```bash
   # Backup do modelo atual
   ssh nas "cp -a /var/lib/ollama/models/trading-analyst /tmp/trading-analist.bak"
   ```

2. **Deploy do novo modelo:**
   ```bash
   # Pull do novo Modelfile
   ssh nas "ollama pull trading-analyst:latest"
   ```

3. **Health check:**
   ```bash
   # Verifica se o modelo responde
   curl -s http://nas:11436/api/tags | jq '.models[] | select(.name=="trading-analyst")'
   ```

4. **Rollback se necessário:**
   ```bash
   ssh nas "ollama rm trading-analyst:latest && \
            cp -a /tmp/trading-analyst.bak /var/lib/ollama/models/trading-analyst"
   ```

**Regra crítica (AGENTS.md política 2b):** modelos `trading-*` nunca são
evictados. Se `trading-analyst` está num endpoint, aquele endpoint não pode
despejá-lo nem receber auxiliar que o compita (`GPU_COORD_PROTECTED_MODELS`).

## 7. Checklist Anti-Regressão

Antes de cada PR para main:

- [ ] `make test` passa localmente
- [ ] `make lint` (ruff) sem erros
- [ ] Pre-commit hook passa (15/15 checks)
- [ ] Pre-push hook passa (ruff + pytest smoke)
- [ ] Novo código tem testes correspondentes
- [ ] Sem marcadores de incompletude (stubs, NotImplementedError)
- [ ] Sem tokens hardcodeados (pre-commit check 1)
- [ ] CMDB baseline atualizado (pre-commit check 9)
- [ ] Sem UIDs duplicados de Grafana (pre-commit check 7)

## 8. Ferramentas Recomendadas (não obrigatórias)

- **`ruff`**: `pip install ruff` — lint ultra-rápido (já integrado nos hooks)
- **`mutmut`**: `pip install mutmut` — teste de mutação para medir eficácia
  da suíte de testes (não instalado ainda, recomendado para trading agent)
- **`pre-commit` framework**: `.pre-commit-config.yaml` (não usado —
  hooks custom do homelab cobrem o necessário)

## 9. Referências

- Martin Fowler, "Continuous Integration" (2024)
- Atlassian, "Continuous Delivery / Software Testing"
- git-tower, "Git Hooks" guide
- AGENTS.md (políticas do homelab RPA4All)
- `docs/DECISION_TRADING_ANALYST_NAS_2026-08-12.md` (decisão NAS)
