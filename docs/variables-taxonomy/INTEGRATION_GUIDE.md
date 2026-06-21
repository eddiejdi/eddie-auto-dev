# 🎯 Variables Catalog Integration Guide

## Quick Start

The **Variables Catalog System** provides comprehensive documentation of all environment variables in your homelab.

### Generated Files

```
.variables-catalog/
├── catalog.json              # Complete catalog (1838 variables)
├── catalog.csv               # Spreadsheet format
├── CATALOG_REPORT.md         # Human-readable report
├── SERVICE_VARIABLES.md      # Variables grouped by service
├── schema.json               # JSON Schema for validation
└── config.py                 # Scanner configuration
```

### Regenerate Catalog

Whenever you add new variables, regenerate the catalog:

```bash
# Scan and catalog all variables
python3 tools/catalog_variables.py

# Generate reports
python3 tools/catalog_reporter.py --all
```

---

## 📊 Key Statistics

| Metric | Value |
|--------|-------|
| **Total Variables** | 1,838 |
| **Source Files** | 140 |
| **Sensitive Variables** | 111 (6.0%) |
| **String Variables** | 1,365 (74.3%) |
| **Boolean Flags** | 211 (11.5%) |
| **Service Variables** | 1,609 (87.5%) |

### Top 5 Categories

1. **Services** (1,609) - API endpoints, hosts, ports, URLs
2. **Authentication** (111) - Tokens, secrets, credentials, keys
3. **Database** (51) - PostgreSQL, Redis, MongoDB connections
4. **Trading** (32) - Exchange APIs, strategies, positions
5. **Monitoring** (17) - Grafana, Prometheus, alerting

---

## 🔐 Sensitive Variables Detection

111 variables marked as sensitive (6.0%):

```bash
# Find all sensitive variables
grep '"sensitive": true' .variables-catalog/catalog.json

# Export to vault
python3 tools/catalog_reporter.py --secrets-only
```

**Sensitive keywords detected:**
- `secret`, `password`, `token`, `key`, `apikey`
- `auth`, `credential`, `private`, `oauth`, `jwt`, `bearer`
- `access_token`, `refresh_token`, `seed`, `private_key`

---

## 🔍 Usage Examples

### Find variables for a specific service

```bash
# Search catalog for variables
cat .variables-catalog/catalog.json | jq '.categories[] | .[] | select(.location.service == "btc_trading_agent")'

# Or use the service report
grep -A 50 "btc_trading_agent" .variables-catalog/SERVICE_VARIABLES.md
```

### Search by variable name pattern

```bash
# All database variables
python3 -c "
import json
with open('.variables-catalog/catalog.json') as f:
    cat = json.load(f)
    for var_name in sorted(cat['categories']['database'].keys()):
        print(var_name)
"
```

### Find variables of a specific type

```bash
# All URL variables
cat .variables-catalog/catalog.json | jq '.categories[] | .[] | select(.type == "url")'

# All boolean flags
cat .variables-catalog/catalog.json | jq '.categories[] | .[] | select(.type == "boolean")'
```

### Export for documentation

```bash
# Generate CSV
python3 tools/catalog_reporter.py --csv

# Generate markdown
python3 tools/catalog_reporter.py --markdown

# Get service breakdown
python3 tools/catalog_reporter.py --services
```

---

## 🏗️ Architecture Integration

### Services Mapped

The catalog automatically discovers variables from:

#### Trading Systems
- **btc_trading_agent** - Bitcoin trading with MT5
- **clear_trading_agent** - Strategy clearing and liquidation

#### Communication
- **telegram_bot** - Telegram integration
- **eddie-telegram-bot** - Advanced bot features

#### Data Management
- **wiki** - Wiki.js knowledge base
- **rpa4all-snapshot** - RPA snapshot management
- **nextcloud** - File sharing platform

#### Infrastructure
- **ollama** - Local LLM (dual GPU)
- **grafana** - Monitoring dashboards
- **prometheus** - Metrics collection
- **postgres** - Main database (schema: btc)

#### Specialized Agents
- **marketing-api** - Marketing automation
- **banking-metrics-exporter** - Financial metrics
- **tape-component-quality** - LTO tape monitoring
- **ollama-gpu-coordinator** - GPU resource management

---

## 📝 Adding New Variables

### Step 1: Define Variables

Add to your `.env` file or service config:
```bash
# Example: New trading parameter
TRADING_NEW_PARAMETER=value
TRADING_NEW_PARAMETER_DESCRIPTION="Parameter description"
```

### Step 2: Document in Code

Add docstring/comment:
```python
import os

# TRADING_NEW_PARAMETER: New trading parameter
new_param = os.getenv("TRADING_NEW_PARAMETER", "default_value")
```

### Step 3: Regenerate Catalog

```bash
python3 tools/catalog_variables.py
python3 tools/catalog_reporter.py --all
```

### Step 4: Commit

```bash
git add .variables-catalog/
git commit -m "docs: update variables catalog with new trading parameters"
```

---

## 🔄 Integration with Communication Bus

### Publish Variable Changes

```python
from specialized_agents.agent_communication_bus import AgentCommunicationBus

bus = AgentCommunicationBus()

# Notify about variable change
bus.publish_message({
    "type": "variable_update",
    "variable": "TRADING_DRY_RUN",
    "old_value": "true",
    "new_value": "false",
    "service": "btc_trading_agent",
    "timestamp": datetime.now().isoformat()
})
```

### Subscribe to Variable Updates

```python
def on_variable_update(message):
    if message["type"] == "variable_update":
        print(f"Variable {message['variable']} changed in {message['service']}")

bus.subscribe("variable_update", on_variable_update)
```

---

## 🛡️ Secrets Management

### Sensitive Variable Handling

Sensitive variables are **never exported** in reports:

```json
{
  "API_KEY": {
    "name": "API_KEY",
    "value": "***REDACTED***",
    "sensitive": true
  }
}
```

### Using the Secrets Agent

```python
from tools.vault.secret_store import SecretStore

secrets = SecretStore()

# Store sensitive variable
secrets.set("trading/exchange_api_key", "sk_live_...")

# Retrieve
api_key = secrets.get("trading/exchange_api_key")
```

### Vault Integration

Link variables to Bitwarden/HashiCorp Vault:

```json
{
  "secrets-mapping": {
    "EXCHANGE_API_KEY": {
      "vault": "bitwarden",
      "collection": "trading",
      "itemId": "uuid-123"
    }
  }
}
```

---

## 🧪 Testing Variables

### Validate Configuration

```bash
# Check variables against schema
python3 -m jsonschema -i .variables-catalog/catalog.json .variables-catalog/schema.json

# Run variable tests
python3 -m pytest tests/test_catalog_variables.py -v
```

### Consistency Checks

```python
import json

with open(".variables-catalog/catalog.json") as f:
    catalog = json.load(f)

# Find variables used but not documented
# Find documented variables not used in code
# Detect naming inconsistencies
```

---

## 📚 Related Documentation

- [Variables Scanner](./README.md) - Scanner configuration and usage
- [Service Architecture](../docs/ARCHITECTURE.md) - System components
- [Deployment Guide](../DEPLOYMENT_GUIDE.md) - Service setup
- [Configuration Management](../docs/CONFIG_MANAGEMENT.md) - Config best practices

---

## 🚀 Next Steps

1. **Review sensitive variables** - Verify all secrets are properly marked
2. **Integrate with monitoring** - Export metrics to Grafana
3. **Setup variable validation** - Enforce schema in CI/CD
4. **Create dashboards** - Visualize variable usage across services
5. **Document dependencies** - Link variable changes to service restart requirements

---

## 📞 Support

For questions about specific variables:

1. **Check catalog**: `grep "VARIABLE_NAME" .variables-catalog/catalog.json`
2. **Review service docs**: See [SERVICE_VARIABLES.md](./SERVICE_VARIABLES.md)
3. **Check source**: Look at original `.env` or config file
4. **Search tests**: `grep -r "VARIABLE_NAME" tests/`

---

**Last Updated:** 2026-06-21  
**Catalog Version:** 1.0.0  
**Total Coverage:** 1,838 variables across 140 source files
