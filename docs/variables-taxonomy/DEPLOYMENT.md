# 🚀 Variables Catalog - Deployment Guide

Complete setup and deployment instructions for the Variables Catalog System.

## Quick Start (5 minutes)

### 1. Run Scanner

```bash
cd /workspace/eddie-auto-dev
python3 tools/catalog_variables.py
```

**Output:**
- `.variables-catalog/catalog.json` - Main catalog (1838 variables)
- `.variables-catalog/catalog.csv` - Spreadsheet export

### 2. Generate Reports

```bash
python3 tools/catalog_reporter.py --all
```

**Output:**
- `CATALOG_REPORT.md` - Human-readable summary
- `SERVICE_VARIABLES.md` - Per-service breakdown
- `catalog.csv` - Spreadsheet format

### 3. View Results

```bash
# View report
cat .variables-catalog/CATALOG_REPORT.md

# Or search catalog
grep "API_KEY" .variables-catalog/catalog.json | head -5
```

---

## Complete Installation (Production)

### Prerequisites

```bash
# Ensure Python 3.8+
python3 --version

# Install dependencies
pip3 install pyyaml jsonschema

# Verify pytest for tests
python3 -m pytest --version
```

### Step 1: Verify Scanner

```bash
cd /workspace/eddie-auto-dev

# Run tests
python3 -m pytest tests/test_catalog_variables.py -v

# Output should show: 25 passed
```

### Step 2: Initial Catalog Generation

```bash
# Generate initial catalog
python3 tools/catalog_variables.py

# Verify output
ls -lh .variables-catalog/
# Total size should be ~500KB
```

### Step 3: Generate All Reports

```bash
# Create markdown, CSV, and service reports
python3 tools/catalog_reporter.py --all

# Verify
ls -lh .variables-catalog/*.{json,csv,md}
```

### Step 4: Commit to Git

```bash
git add .variables-catalog/ docs/variables-taxonomy/
git commit -m "chore: initialize variables catalog system

- Scanner: 1838 variables from 140 source files
- Categories: authentication, database, trading, services
- Reports: markdown, CSV, service breakdown
- Coverage: complete homelab infrastructure"

git push
```

---

## 🔄 Automated Updates (systemd)

### Option 1: Weekly Update Service

**File:** `/etc/systemd/system/variables-catalog-update.service`

```ini
[Unit]
Description=Update Variables Catalog
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=edenilson
WorkingDirectory=/workspace/eddie-auto-dev
ExecStart=/usr/bin/python3 /workspace/eddie-auto-dev/tools/catalog_updater.py
StandardOutput=journal
StandardError=journal
```

**File:** `/etc/systemd/system/variables-catalog-update.timer`

```ini
[Unit]
Description=Weekly Variables Catalog Update
Requires=variables-catalog-update.service

[Timer]
OnCalendar=weekly
OnCalendar=Mon *-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Enable:**

```bash
sudo cp variables-catalog-update.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable variables-catalog-update.timer
sudo systemctl start variables-catalog-update.timer

# Check status
sudo systemctl status variables-catalog-update.timer
sudo journalctl -u variables-catalog-update -f
```

### Option 2: Scheduled via crontab

```bash
# Edit crontab
crontab -e

# Add weekly update (every Monday at 2am)
0 2 * * 1 cd /workspace/eddie-auto-dev && python3 tools/catalog_updater.py >> /var/log/variables-catalog.log 2>&1

# Or daily update
0 * * * * cd /workspace/eddie-auto-dev && python3 tools/catalog_updater.py --no-commit >> /var/log/variables-catalog.log 2>&1
```

### Option 3: Continuous Monitoring

```bash
# Run updater in loop mode (check every 3600 seconds)
python3 tools/catalog_updater.py --loop 3600 --sync

# Or as systemd oneshot service that runs periodically
# (Recommended for production)
```

---

## 🔌 Integration with Communication Bus

### Automatic Notifications

When catalog updates, the system automatically notifies the Communication Bus:

```python
# Event published to bus
{
    "type": "variables_updated",
    "timestamp": "2026-06-21T02:15:00.000000",
    "added": 5,
    "removed": 0,
    "modified": true
}
```

### Subscribe to Updates

```python
from specialized_agents.agent_communication_bus import AgentCommunicationBus

def on_variables_updated(message):
    print(f"Catalog updated: {message['added']} new variables")

bus = AgentCommunicationBus()
bus.subscribe("variables_updated", on_variables_updated)
```

---

## 📊 CI/CD Integration

### GitHub Actions

**File:** `.github/workflows/catalog-check.yml`

```yaml
name: Variables Catalog Check

on:
  push:
    paths:
      - '.env*'
      - 'docker-compose*.yml'
      - 'systemd/*.service'
      - '**/config.py'
      - '**/settings.py'

jobs:
  update-catalog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pyyaml jsonschema pytest
      
      - name: Run tests
        run: python -m pytest tests/test_catalog_variables.py -v
      
      - name: Generate catalog
        run: python tools/catalog_variables.py
      
      - name: Generate reports
        run: python tools/catalog_reporter.py --all
      
      - name: Commit changes
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .variables-catalog/ docs/variables-taxonomy/
          git commit -m "chore: auto-update variables catalog" || exit 0
          git push
```

---

## 🧪 Testing & Validation

### Unit Tests

```bash
# Run all tests
python3 -m pytest tests/test_catalog_variables.py -v

# With coverage
python3 -m pytest tests/test_catalog_variables.py --cov=tools.catalog_variables --cov-report=html

# Expected: 25/25 passing
```

### Validation Against Schema

```bash
# Validate JSON against schema
python3 -m jsonschema -i .variables-catalog/catalog.json .variables-catalog/schema.json

# No output = valid
```

### Manual Verification

```bash
# Check total variables
python3 -c "import json; cat = json.load(open('.variables-catalog/catalog.json')); print(f'Total: {cat[\"metadata\"][\"totalVariables\"]} variables')"

# Count by type
python3 tools/catalog_reporter.py --stats

# Verify no duplicates
cat .variables-catalog/catalog.csv | cut -d, -f1 | sort | uniq -d
# Should output nothing
```

---

## 📈 Monitoring & Analytics

### Track Changes Over Time

```bash
# Create history file
mkdir -p .variables-catalog/history

# Timestamp each catalog
cp .variables-catalog/catalog.json ".variables-catalog/history/catalog-$(date +%Y%m%d-%H%M%S).json"

# Analyze trends
python3 << 'EOF'
import json
import glob

catalogs = sorted(glob.glob('.variables-catalog/history/catalog-*.json'))
for catalog_file in catalogs[-5:]:  # Last 5
    with open(catalog_file) as f:
        cat = json.load(f)
        total = cat['metadata']['totalVariables']
        timestamp = catalog_file.split('-')[-1].replace('.json', '')
        print(f"{timestamp}: {total} variables")
EOF
```

### Export to Prometheus

```python
# Create metrics exporter
# .variables-catalog/prometheus_exporter.py

from prometheus_client import Counter, Gauge, start_http_server
import json

# Metrics
total_vars = Gauge('catalog_total_variables', 'Total variables in catalog')
sensitive_vars = Gauge('catalog_sensitive_variables', 'Count of sensitive variables')
var_by_type = Gauge('catalog_variables_by_type', 'Variables by type', ['type'])

# Update metrics
with open('.variables-catalog/catalog.json') as f:
    cat = json.load(f)
    total = cat['metadata']['totalVariables']
    total_vars.set(total)
    
    # Count sensitive
    sensitive = sum(1 for c in cat['categories'].values() 
                   for v in c.values() if v.get('sensitive'))
    sensitive_vars.set(sensitive)

# Start exporter
start_http_server(8000)
```

---

## 🛠️ Troubleshooting

### Scanner Finds No Variables

```bash
# Check if files exist
find . -name "*.env" -type f | head -5
find . -name "docker-compose*.yml" -type f | head -5

# Run with verbose output
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from tools.catalog_variables import VariablesCatalog
cat = VariablesCatalog()
cat.generate_catalog()
"
```

### Reports Not Generated

```bash
# Check dependencies
python3 -c "import yaml, jsonschema; print('OK')"

# Run reporter with error output
python3 tools/catalog_reporter.py --all 2>&1 | tail -20
```

### Git Commit Fails

```bash
# Check git status
git status

# Clean up if needed
git clean -fd
git restore .

# Then run updater
python3 tools/catalog_updater.py --no-commit
```

---

## 🔐 Security Best Practices

1. **Never commit secrets** - They're marked as `***REDACTED***` in exports
2. **Validate with schema** - Before importing catalog into external systems
3. **Control access** - .variables-catalog/ should have restricted permissions
4. **Use secrets vault** - Map sensitive variables to Bitwarden/Vault
5. **Audit changes** - Monitor who/when variables are updated

```bash
# Restrict permissions
chmod 750 .variables-catalog/
chmod 640 .variables-catalog/*.json

# Audit changes
git log --oneline .variables-catalog/ | head -20
```

---

## 📚 Related Documentation

- [README](./README.md) - Overview and features
- [Integration Guide](./INTEGRATION_GUIDE.md) - Usage examples
- [Services Overview](./SERVICES_OVERVIEW.md) - Service mappings
- [Catalog Report](./CATALOG_REPORT.md) - Current variables

---

## 🎯 Next Steps

1. **✅ Run initial scan** - Generate baseline catalog
2. ✅ **Add to git** - Commit catalog system
3. **Setup automation** - Schedule weekly updates via systemd
4. **Monitor changes** - Track catalog evolution over time
5. **Integrate dashboards** - Export metrics to Grafana
6. **Team documentation** - Share reports with team

---

**Deployment Status:** ✅ Production Ready  
**Test Coverage:** 25/25 passing  
**Last Updated:** 2026-06-21
