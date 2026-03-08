# Environment Configuration Guide

## Overview

Consolidamos múltiplos arquivos `.env` em um único template `.env.consolidated`:
- `.env.mailu` → Email Server
- `.env.jira` → Jira Integration
- `.env.email` → Email Client
- `btc_trading_agent/.env` → KuCoin Trading

## Quick Start

```bash
# Copy template to local
cp .env.consolidated .env

# Edit with your real credentials
nano .env

# Validate
./env_merge_validator.sh
```

## Components

| Component | Variables | Location |
|-----------|-----------|----------|
| **Google Cloud** | `GOOGLE_AI_API_KEY`, `GEMINI_ENABLED` | Lines 11-22 |
| **Home Assistant** | `HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN` | Lines 24-25 |
| **Mailu Email** | `MAILU_DOMAIN`, `MAILU_SECRET_KEY`, ports | Lines 27-53 |
| **Jira** | `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Lines 55-58 |
| **Email Client** | `EMAIL_DB_PASSWORD`, `EMAIL_DOMAIN` | Lines 60-63 |
| **BTC Trading** | `KUCOIN_API_KEY`, `KUCOIN_API_SECRET` | Lines 65-69 |
| **Ollama** | `OLLAMA_HOST`, `OLLAMA_HOST_GPU1` | Lines 71-74 |
| **PostgreSQL** | `DB_HOST`, `DATABASE_URL` | Lines 76-82 |
| **Communication** | `COMMUNICATION_BUS_URL` | Lines 84-87 |

## Security

✅ `.env` is in `.gitignore` (never committed)
✅ `.env.consolidated` only has placeholders (safe to commit)
✅ Never store real credentials in version control

```bash
# Protect your local .env
chmod 600 .env
```

## Validation Commands

```bash
# Run validator
bash env_merge_validator.sh

# Check for placeholder values (should have none in production)
grep "your_" .env | wc -l

# Verify no duplicates
cut -d'=' -f1 .env | sort | uniq -d
```

## Troubleshooting

- **Missing required keys**: Run `./env_merge_validator.sh` → shows which keys
- **Duplicate DATABASE_URL**: Keep only one (Mailu uses MAILU_DATABASE_URL, BTC uses DATABASE_URL)
- **Token issues**: Ensure `JIRA_API_TOKEN` is not password (use "API token" from Jira)

See [Merge Guide](ENV_MERGE_GUIDE.md) for detailed setup.
