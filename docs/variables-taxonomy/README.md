# 📋 Homelab Variables Catalog

## Overview

Complete documentation of all environment variables, system variables, and configuration parameters across your homelab and integrated systems.

**Last Updated**: 2026-06-21  
**Total Variables**: Auto-scanned  
**Coverage**: .env | docker-compose | systemd | Python | YAML | Secrets

---

## 🎯 Purpose

- **Single source of truth** for all system variables
- **Prevent configuration drift** between environments
- **Security audit** of secrets and sensitive data
- **Dependency mapping** between components
- **Onboarding documentation** for new services

---

## 📊 Structure

```
.variables-catalog/
├── schema.json              # JSON Schema for validation
├── catalog.json             # Generated catalog (auto-updated)
├── taxonomy.json            # Semantic organization
├── secrets-mapping.json     # Secrets ↔ Vault mappings
├── dependencies.json        # Variable dependencies graph
└── README.md               # This file
```

---

## 🔄 Generation & Maintenance

### Run Scanner
```bash
# Generate catalog from all sources
python3 tools/catalog_variables.py

# Or with custom output
python3 tools/catalog_variables.py --output docs/variables-taxonomy/catalog.json
```

**Sources Scanned:**
- ✅ `.env` files (all variants)
- ✅ `docker-compose*.yml`
- ✅ `systemd/*.service` files
- ✅ Python `*config*.py`, `*settings*.py`
- ✅ YAML configuration files
- ✅ Shell scripts with `export` statements

### Categories

The catalog automatically organizes variables:

| Category | Pattern | Examples |
|----------|---------|----------|
| **Database** | `DATABASE`, `DB_`, `POSTGRES`, `REDIS` | `DATABASE_URL`, `DB_HOST` |
| **Services** | `API`, `SERVICE`, `HOST`, `PORT`, `URL` | `API_PORT`, `SERVICE_HOST` |
| **Authentication** | `AUTH`, `TOKEN`, `SECRET`, `KEY`, `JWT` | `API_KEY`, `JWT_SECRET` |
| **Trading** | `TRADING`, `EXCHANGE`, `MT5`, `CRYPTO` | `EXCHANGE_API_KEY` |
| **Infrastructure** | `DOCKER`, `KUBERNETES`, `STORAGE`, `VOLUME` | `DOCKER_REGISTRY_URL` |
| **Integrations** | `SLACK`, `TELEGRAM`, `GITHUB`, `WEBHOOK` | `TELEGRAM_BOT_TOKEN` |
| **Monitoring** | `MONITORING`, `LOGGING`, `GRAFANA`, `PROMETHEUS` | `GRAFANA_ADMIN_PASSWORD` |

---

## 🛡️ Enforcement — hook obrigatório multi-agente

O catálogo deixou de ser só documentação passiva: `tools/hooks/variable_registry_validate.py`
consulta `.variables-catalog/catalog.json` **antes** de qualquer agente criar uma variável nova,
e bloqueia duplicatas de taxonomia (ex: `API_TOKEN` vs `APITOKEN` vs `Api_Token`).

| Camada | Ferramentas cobertas | Comportamento |
|--------|----------------------|----------------|
| `PreToolUse` hook (`.claude/settings.json`, `hooks.json`, `.cursor/hooks.json`, `.grok/hooks/claude-code-import.json`) | Claude Code, Cursor, Grok | Duplicata → `deny` (bloqueia a edição). Nome novo/fora do padrão → `warn` (não bloqueia, só avisa). |
| `git pre-commit` (`scripts/git-hooks/pre-commit`, instalar com `bash scripts/git-hooks/install.sh`) | **Qualquer ferramenta**, inclusive Codex e edição manual | Duplicata → bloqueia o commit local. |
| CI (`.github/workflows/variable-registry-check.yml`) | Qualquer PR, independente do hook local estar instalado | Duplicata → falha o check do PR. |

**Nota sobre Codex**: `.codex/config.json` referencia `hooks_path: hooks.json` só como metadado
informativo — o Codex CLI não consome hooks `PreToolUse` nativamente hoje. Para Codex, a única
camada garantida é o pre-commit + CI acima.

Quando o hook bloqueia uma duplicata, a mensagem já indica o nome canônico existente para reutilizar.
Quando só avisa (nome genuinamente novo), o fluxo esperado é: documentar o propósito aqui/no
serviço correspondente e rodar `python3 tools/catalog_variables.py` para reindexar.

---

## 🔐 Secrets Management

### Sensitive Variables Detection

Variables containing keywords below are automatically marked as `sensitive: true`:
- `secret`, `password`, `token`, `key`, `api_key`
- `auth`, `credential`, `private`, `oauth`, `jwt`, `bearer`
- `access_token`, `refresh_token`, `seed`

**Values are never exposed in catalog** — replaced with `***REDACTED***`

### Mapping to Vault

Create `secrets-mapping.json` to link variables to Vault/Bitwarden:

```json
{
  "API_KEY_EXCHANGE": {
    "vault": "bitwarden",
    "collection": "trading",
    "itemId": "uuid-123",
    "field": "api_key"
  },
  "JWT_SECRET": {
    "vault": "hashicorp-vault",
    "path": "secret/data/api/jwt",
    "field": "secret"
  }
}
```

---

## 📦 Your Systems Overview

### Trading Bots
- **BTC Trading Agent** (`btc_trading_agent/`)
  - Variables: `EXCHANGE_*`, `TRADING_*`, `MT5_*`
  - Dependencies: PostgreSQL, Redis, Ollama
  
- **Clear Trading Agent** (`clear_trading_agent/`)
  - Variables: `STRATEGY_*`, `RISK_*`, `EXCHANGE_*`
  - Dependencies: Trading DB, Market data feeds

### Communication
- **Telegram Bot** (`telegram_bot.py`)
  - Variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - Dependencies: Telegram API

### Data & Storage
- **RPA4All** (Snapshot management)
  - Variables: `RPA_*`, `SNAPSHOT_*`
  - Dependencies: S3/Minio, PostgreSQL

- **Wiki** (Wiki.js + knowledge base)
  - Variables: `WIKI_*`, `POSTGRES_*`
  - Dependencies: PostgreSQL, Nextcloud

### Infrastructure
- **Ollama** (Local LLM)
  - Variables: `OLLAMA_*`, `GPU_*`
  - Dependencies: GPU drivers, VRAM allocation

- **Docker** Services
  - Grafana, Prometheus, Authentik, etc.

- **Systemd Services**
  - Agents, API servers, background jobs

---

## 🗂️ Catalog Structure (JSON)

### Variable Entry

```json
{
  "API_KEY_EXCHANGE": {
    "name": "API_KEY_EXCHANGE",
    "displayName": "Exchange API Key",
    "type": "secret",
    "source": ".env",
    "description": "API key for cryptocurrency exchange integration",
    "default": null,
    "example": "sk_live_...",
    "required": true,
    "sensitive": true,
    "location": {
      "file": ".env",
      "line": 42,
      "service": "btc_trading_agent"
    },
    "relatedVariables": [
      "EXCHANGE_ENDPOINT",
      "EXCHANGE_SECRET"
    ],
    "validationRules": {
      "pattern": "^sk_[a-z0-9]{40,}$",
      "minLength": 20
    },
    "lastModified": "2026-06-21T10:00:00Z",
    "status": "active",
    "owner": "trading-team"
  }
}
```

---

## 🔍 Usage Examples

### Find all database variables
```bash
cat .variables-catalog/catalog.json | jq '.categories.database'
```

### Find sensitive variables
```bash
cat .variables-catalog/catalog.json | jq '.categories[] | .[] | select(.sensitive == true)'
```

### Find variables for a specific service
```bash
cat .variables-catalog/catalog.json | jq '.categories[] | .[] | select(.location.service == "trading_agent")'
```

### Check variable dependencies
```bash
cat .variables-catalog/dependencies.json | jq '.API_KEY_EXCHANGE'
```

### Validate against schema
```bash
python3 -m jsonschema -i .variables-catalog/catalog.json .variables-catalog/schema.json
```

---

## 📋 Integration with Services

### Docker Compose
Variables from `docker-compose.yml` are automatically extracted:
```yaml
services:
  postgres:
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      # → Catalogued as: POSTGRES_USER, POSTGRES_PASSWORD
```

### Systemd Services
Variables from `systemd/*.service`:
```ini
[Service]
Environment="OLLAMA_HOST=http://192.168.15.2:11434"
# → Catalogued as: OLLAMA_HOST
```

### Python Applications
Variables referenced in code:
```python
import os
api_key = os.getenv("API_KEY_EXCHANGE")
# → Catalogued as: API_KEY_EXCHANGE
```

---

## 🚀 Best Practices

### ✅ DO
- Use `UPPERCASE_SNAKE_CASE` for variable names
- Keep related variables grouped (prefix with service name)
- Document complex variables with examples
- Update catalog after adding new variables
- Use `.env.example` for non-secret examples

### ❌ DON'T
- Hardcode secrets in code/configs
- Use inconsistent naming conventions
- Mix configuration and secrets in same file
- Leave variables undocumented
- Expose secrets in version control

---

## 📖 Documentation Template

When adding new variables, use this format:

```markdown
## Service: Trading Bot

### Database Variables
- `TRADING_DB_HOST`: PostgreSQL host (required)
  - Type: `url`
  - Example: `localhost:5432`
  - Related: `TRADING_DB_USER`, `TRADING_DB_PASSWORD`

### Exchange Integration
- `EXCHANGE_API_KEY`: Exchange API authentication (required, sensitive)
  - Type: `secret`
  - Related: `EXCHANGE_SECRET`, `EXCHANGE_ENDPOINT`
```

---

## 🔄 Automation

### GitHub Actions Sync
```yaml
- name: Sync Variables Catalog
  run: |
    python3 tools/catalog_variables.py
    git add .variables-catalog/catalog.json
    git commit -m "chore: update variables catalog"
```

### Pre-commit Hook (implementado)
```bash
bash scripts/git-hooks/install.sh   # symlink .git/hooks/pre-commit -> scripts/git-hooks/pre-commit
```
Valida o diff staged contra o catálogo em cada commit — ver seção
[Enforcement](#-enforcement--hook-obrigatório-multi-agente) acima.

---

## 📞 Support

For questions about specific variables:
1. Check `.variables-catalog/catalog.json`
2. Review original service documentation
3. Check `.env.example` files
4. Ask in #infrastructure channel

---

## 📝 Version History

| Date | Changes | Author |
|------|---------|--------|
| 2026-06-21 | Initial catalog generation | Auto-scanner |
| 2026-07-14 | Enforcement hook (PreToolUse + pre-commit + CI); fix DSN-embedded-credential leak in scanner | Infrastructure Agent |

---

## 🏗️ Related Documentation

- [Infrastructure Setup](../DEPLOYMENT_GUIDE.md)
- [Service Configuration](./services-config/)
- [Secrets Management](./secrets-management/)
- [System Architecture](./architecture/)

