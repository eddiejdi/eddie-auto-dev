# 📦 System Components & Their Variables

Complete mapping of all homelab services and their environment variables.

## 🎯 Quick Reference

| Service | Variables | Type | Status |
|---------|-----------|------|--------|
| **Core Infrastructure** |
| PostgreSQL | 51 | Database | ✅ Active |
| Ollama (GPU0) | 12 | LLM | ✅ Active |
| Ollama (GPU1) | 8 | LLM | ✅ Active |
| **Trading Systems** |
| BTC Trading Agent | 32 | Bot | ✅ Active |
| Clear Trading Agent | 18 | Bot | ✅ Active |
| **Communication** |
| Telegram Bot | 14 | Bot | ✅ Active |
| **Data & Knowledge** |
| Wiki.js | 28 | CMS | ✅ Active |
| Nextcloud | 35 | Storage | ✅ Active |
| RPA4All | 22 | Automation | ✅ Active |
| **Monitoring & Observability** |
| Grafana | 89 | Dashboard | ✅ Active |
| Prometheus | 45 | Metrics | ✅ Active |
| Alertmanager | 23 | Alerts | ✅ Active |
| **Infrastructure Services** |
| Docker Services | 156 | Orchestration | ✅ Active |
| Systemd Services | 287 | Process Management | ✅ Active |

---

## 🗺️ Service Dependency Map

```
┌─────────────────────────────────────────────────────┐
│           PostgreSQL (Schema: btc)                  │
│        Database Hub (PORT: 5433)                    │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    │            │            │              │
    ▼            ▼            ▼              ▼
[Trading]   [Wiki.js]    [Nextcloud]   [Monitoring]
  Agents    POSTGRES_    DB_PASSWORD   DATASOURCES
  
┌────────────────────────────────────────────┐
│     Ollama LLM (Dual GPU)                  │
│  GPU0: 11434  │  GPU1: 11435              │
└────────────────────────────────────────────┘
    │                        │
    ▼                        ▼
[Trading Agents]      [RAG Reindexing]

┌──────────────────────────────────────────────┐
│   Communication Bus (8503)                   │
│   Agent IPC & Coordination                   │
└──────────────────────────────────────────────┘
    │
    ├─→ [Telegram Bot]
    ├─→ [Trading Agents]
    ├─→ [Specialized Agents]
    └─→ [Monitoring Exporters]
```

---

## 🔐 Security & Secrets

### Authentication Variables (111 total)
```
AUTHENTIK_*                     - Single Sign-On (OIDC)
JWT_SECRET                      - API authentication
API_KEY_*                       - Service API keys
EXCHANGE_API_*                  - Trading exchange credentials
TELEGRAM_BOT_TOKEN              - Telegram bot authentication
POSTGRES_PASSWORD               - Database password
REDIS_PASSWORD                  - Cache password
```

### By Sensitivity Level

| Level | Count | Notes |
|-------|-------|-------|
| 🔒 **Critical** | 23 | Never expose (passwords, exchange keys) |
| 🟡 **Sensitive** | 88 | Handle carefully (tokens, API keys) |
| ✅ **Public** | 1,727 | Safe to share (endpoints, ports) |

---

## 🏗️ Detailed Service Breakdown

### Core Database Layer

**PostgreSQL (PORT: 5433)**
```
POSTGRES_HOST                   Connection host
POSTGRES_PORT                   Connection port (5433)
POSTGRES_USER                   Admin user
POSTGRES_PASSWORD               Admin password
POSTGRES_DB                     Default database (btc)
POSTGRES_INITDB_ARGS            Init arguments
```

**Redis Cache (PORT: 6379)**
```
REDIS_HOST                      Cache server host
REDIS_PORT                      Cache port
REDIS_PASSWORD                  Cache password (if auth enabled)
REDIS_DB                        Database index
```

### Trading Systems

**BTC Trading Agent**
```
TRADING_DRY_RUN                 Enable dry-run mode (boolean)
EXCHANGE_ENDPOINT               Exchange API endpoint
EXCHANGE_API_KEY                Exchange API key (sensitive)
EXCHANGE_SECRET                 Exchange secret (sensitive)
MT5_ACCOUNT                     MT5 account number
MT5_PASSWORD                    MT5 password (sensitive)
DATABASE_URL                    Connection string
STRATEGY_MODE                   Trading mode (enum)
RISK_THRESHOLD                  Risk limit (0.0-1.0)
```

**Clear Trading Agent**
```
LIQUIDATION_ENABLED             Enable liquidation (boolean)
LIQUIDATION_THRESHOLD           Liquidation trigger (%)
CLEAR_STRATEGY                  Clearing strategy
DATABASE_URL                    Connection string
OLLAMA_HOST                     LLM endpoint
```

### Communication & Integration

**Telegram Bot**
```
TELEGRAM_BOT_TOKEN              Bot API token (sensitive)
TELEGRAM_CHAT_ID                Default chat ID
TELEGRAM_API_URL                Telegram API endpoint
DATABASE_URL                    State persistence
```

**Wiki.js**
```
WIKI_DB_HOST                    Database host
WIKI_DB_USER                    Database user
WIKI_DB_PASSWORD                Database password (sensitive)
WIKI_JWT_SECRET                 Authentication secret
WIKI_ADMIN_PASSWORD             Admin password (sensitive)
WIKI_URL                        Public URL
```

**Nextcloud**
```
NEXTCLOUD_DB_HOST               Database host
NEXTCLOUD_DB_PASSWORD           Database password (sensitive)
NEXTCLOUD_ADMIN_USER            Admin username
NEXTCLOUD_ADMIN_PASSWORD        Admin password (sensitive)
NEXTCLOUD_TRUSTED_DOMAINS       Allowed domains
NEXTCLOUD_REDIS_HOST            Cache server
```

### Monitoring & Observability

**Grafana**
```
GF_ADMIN_PASSWORD               Admin password (sensitive)
GF_SECURITY_ADMIN_USER          Admin username
GF_SECURITY_SECRET_KEY          Session secret
GF_SECURITY_JWT_SECRET          JWT secret
GF_DATABASE_URL                 Database connection
GF_PATHS_PROVISIONING           Config path
GF_ENABLE_GZIP                  Enable compression
GF_LOG_LEVEL                    Log level
```

**Prometheus**
```
PROMETHEUS_PORT                 Server port (9090)
PROMETHEUS_CONFIG_FILE          Config location
PROMETHEUS_RETENTION            Data retention period
PROMETHEUS_STORAGE_PATH         Storage directory
PROMETHEUS_EXTERNAL_LABELS      Static labels
```

**Alertmanager**
```
ALERTMANAGER_PORT               Server port (9093)
ALERTMANAGER_CONFIG_FILE        Config location
ALERTMANAGER_TEMPLATES_PATH     Templates directory
SLACK_WEBHOOK_URL               Slack integration
TELEGRAM_ALERT_TOKEN            Telegram alerts token
```

### Infrastructure & Orchestration

**Docker Environment**
```
DOCKER_HOST                     Docker socket path
DOCKER_TLS_VERIFY               TLS verification
DOCKER_CERT_PATH                Certificate path
COMPOSE_PROJECT_NAME            Project name
```

**System-wide Paths**
```
DATA_DIR                        Application data directory
LOGS_DIR                        Log files directory
TEMP_DIR                        Temporary files directory
BACKUP_DIR                      Backup directory
```

---

## 🔄 Variable Dependencies

### Critical Chains

```
POSTGRES_PASSWORD
  ├─→ TRADING_AGENT requires DATABASE_URL
  ├─→ WIKI_DB_PASSWORD must match
  ├─→ NEXTCLOUD_DB_PASSWORD must match
  └─→ GRAFANA GF_DATABASE_URL

OLLAMA_HOST
  ├─→ TRADING_AGENT uses for ML inference
  ├─→ RAG_REINDEX uses for embeddings
  └─→ SPECIALIZED_AGENTS for NLP tasks

JWT_SECRET
  ├─→ API authentication
  ├─→ Wiki.js session management
  └─→ Grafana authentication
```

### Optional Dependencies

```
REDIS_HOST → Optional cache for:
  - Session storage (API, Wiki)
  - Rate limiting (API)
  - Metrics caching (Monitoring)
  - Job queue (Agents)
```

---

## 📊 Variable Types Distribution

| Type | Count | Examples |
|------|-------|----------|
| **String** | 1,365 | Endpoints, usernames, paths |
| **Boolean** | 211 | Feature flags, debug mode |
| **Integer** | 150 | Ports, timeouts, limits |
| **URL** | 62 | API endpoints, database URLs |
| **Path** | 44 | Directory locations |
| **JSON** | 4 | Complex configuration |
| **Float** | 2 | Ratios, percentages |

---

## 🚀 Environment Profiles

### Development Environment
```
TRADING_DRY_RUN=true
OLLAMA_HOST=http://192.168.15.2:11434
DATABASE_URL=postgresql://dev:dev@localhost:5432/btc_dev
DEBUG=true
LOG_LEVEL=DEBUG
```

### Staging Environment
```
TRADING_DRY_RUN=true
DATABASE_URL=postgresql://staging:***@staging-db:5432/btc
ENVIRONMENT=staging
LOG_LEVEL=INFO
```

### Production Environment
```
TRADING_DRY_RUN=false
DATABASE_URL=postgresql://prod:***@prod-db:5433/btc
ENVIRONMENT=production
LOG_LEVEL=WARNING
ENABLE_MONITORING=true
```

---

## 📝 Adding New Services

When adding a new service:

1. **Create `.env` file with all variables**
   ```bash
   SERVICE_NAME=myservice
   SERVICE_PORT=8080
   SERVICE_DEBUG=false
   ```

2. **Document in Python config**
   ```python
   os.getenv("SERVICE_NAME")
   os.getenv("SERVICE_PORT")
   ```

3. **Regenerate catalog**
   ```bash
   python3 tools/catalog_variables.py
   ```

4. **Update this document**
   ```markdown
   ## My Service
   ```

5. **Commit changes**
   ```bash
   git add .variables-catalog/
   git add docs/variables-taxonomy/
   git commit -m "docs: add My Service variables"
   ```

---

## 🔗 Related Documentation

- [Variables Taxonomy README](./README.md)
- [Integration Guide](./INTEGRATION_GUIDE.md)
- [Catalog Report](./CATALOG_REPORT.md)
- [Service Variables Breakdown](./SERVICE_VARIABLES.md)

---

**Last Updated:** 2026-06-21  
**Services Catalogued:** 20+  
**Total Variables:** 1,838  
**Coverage:** Complete
