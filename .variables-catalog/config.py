#!/usr/bin/env python3
"""
Configuration for Variables Catalog Scanner
Defines scanning rules, paths, and variable classification
"""

from typing import Dict, List, Pattern
import re

# ============================================================================
# SCANNING CONFIGURATION
# ============================================================================

SCAN_CONFIG = {
    # Paths to scan (relative to project root)
    "include_paths": [
        ".",  # Root
        "specialized_agents/",
        "btc_trading_agent/",
        "clear_trading_agent/",
        "telegram_bot/",
        "tools/",
        "config/",
        "docker/",
        "systemd/",
        "docs/",
    ],
    
    # Paths to exclude from scanning
    "exclude_paths": [
        ".git/",
        ".venv/",
        "venv/",
        "node_modules/",
        "__pycache__/",
        ".pytest_cache/",
        "build/",
        "dist/",
        ".egg-info/",
        "*.pyc",
    ],
    
    # File patterns to scan
    "file_patterns": {
        "env": [".env", ".env.*", "*.env"],
        "docker": ["docker-compose.yml", "docker-compose.*.yml", "Dockerfile"],
        "systemd": ["*.service", "*.timer"],
        "python": ["*config.py", "*settings.py", "*constants.py"],
        "yaml": ["*.yml", "*.yaml"],
        "shell": ["*.sh", "*.bash"],
    },
    
    # Skip these specific files (full paths)
    "skip_files": [
        ".variables-catalog/",
        ".github/",
        "docs/variables-taxonomy/",
    ],
}

# ============================================================================
# VARIABLE CLASSIFICATION RULES
# ============================================================================

VARIABLE_CATEGORIES: Dict[str, str] = {
    "database": r"(DATABASE|DB_|POSTGRES|MYSQL|REDIS|MONGODB|ELASTIC|SQL)",
    "services": r"(API|SERVICE|HOST|PORT|URL|ENDPOINT|SERVER|BIND)",
    "authentication": r"(AUTH|TOKEN|SECRET|PASSWORD|KEY|APIKEY|JWT|BEARER|OAUTH)",
    "trading": r"(TRADING|EXCHANGE|MT5|CRYPTO|BTC|ETH|COIN|STRATEGY|POSITION|ORDER)",
    "infrastructure": r"(DOCKER|KUBERNETES|K8S|NETWORK|STORAGE|VOLUME|MOUNT|DISK)",
    "integrations": r"(SLACK|TELEGRAM|GITHUB|GITLAB|WEBHOOK|GOOGLE|AWS|AZURE|CLOUD)",
    "monitoring": r"(MONITORING|LOGGING|GRAFANA|PROMETHEUS|SENTRY|ALERT|METRIC|TRACE)",
    "rpa": r"(RPA|AUTOMATION|WORKFLOW|SNAPSHOT|SCHEDULE|TASK|JOB)",
    "wiki": r"(WIKI|KNOWLEDGE|DOCUMENT|PAGE|CONTENT|MARKDOWN)",
    "security": r"(SECURITY|SSL|TLS|CERT|CIPHER|HASH|SALT|2FA|MFA)",
}

# ============================================================================
# SENSITIVE KEYWORDS
# ============================================================================

SENSITIVE_KEYWORDS = [
    "secret",
    "password",
    "token",
    "key",
    "api_key",
    "apikey",
    "auth",
    "credential",
    "private",
    "oauth",
    "jwt",
    "bearer",
    "access_token",
    "refresh_token",
    "seed",
    "private_key",
    "public_key",
    "cert",
    "certificate",
    "pem",
    "webhook_secret",
    "client_secret",
    "master_key",
]

# ============================================================================
# SERVICE DEFINITIONS
# ============================================================================

SERVICES = {
    "btc_trading_agent": {
        "name": "BTC Trading Agent",
        "description": "Bitcoin trading bot with MT5 integration",
        "vars_prefix": ["TRADING_", "EXCHANGE_", "MT5_", "BTC_"],
        "dependencies": ["DATABASE_URL", "OLLAMA_HOST", "REDIS_URL"],
        "critical_vars": [
            "EXCHANGE_API_KEY",
            "EXCHANGE_SECRET",
            "DATABASE_URL",
            "TRADING_DRY_RUN",
        ],
    },
    
    "clear_trading_agent": {
        "name": "Clear Trading Agent",
        "description": "Strategy clearing and liquidation management",
        "vars_prefix": ["CLEAR_", "LIQUIDATION_", "RISK_"],
        "dependencies": ["DATABASE_URL", "OLLAMA_HOST"],
        "critical_vars": [
            "LIQUIDATION_ENABLED",
            "RISK_THRESHOLD",
            "DATABASE_URL",
        ],
    },
    
    "telegram_bot": {
        "name": "Telegram Bot",
        "description": "Telegram integration and messaging",
        "vars_prefix": ["TELEGRAM_", "CHATBOT_"],
        "dependencies": ["DATABASE_URL"],
        "critical_vars": [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        ],
    },
    
    "api_server": {
        "name": "FastAPI Server",
        "description": "Main API server on port 8503",
        "vars_prefix": ["API_", "SERVER_"],
        "dependencies": ["DATABASE_URL", "JWT_SECRET"],
        "critical_vars": [
            "API_PORT",
            "API_HOST",
            "JWT_SECRET",
            "DATABASE_URL",
        ],
    },
    
    "ollama": {
        "name": "Ollama LLM Engine",
        "description": "Local LLM with dual GPU support",
        "vars_prefix": ["OLLAMA_", "GPU_", "MODEL_"],
        "dependencies": [],
        "critical_vars": [
            "OLLAMA_HOST",
            "OLLAMA_MODELS",
        ],
    },
    
    "postgres": {
        "name": "PostgreSQL Database",
        "description": "Main PostgreSQL database (trading schema)",
        "vars_prefix": ["POSTGRES_", "DATABASE_"],
        "dependencies": [],
        "critical_vars": [
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_HOST",
        ],
    },
    
    "wiki": {
        "name": "Wiki.js",
        "description": "Wiki and knowledge base",
        "vars_prefix": ["WIKI_", "KNOWLEDGE_"],
        "dependencies": ["POSTGRES_HOST"],
        "critical_vars": [
            "WIKI_DB_HOST",
            "WIKI_DB_PASSWORD",
        ],
    },
    
    "nextcloud": {
        "name": "Nextcloud",
        "description": "File sharing and collaboration",
        "vars_prefix": ["NEXTCLOUD_", "NC_"],
        "dependencies": ["POSTGRES_HOST", "REDIS_HOST"],
        "critical_vars": [
            "NEXTCLOUD_DB_PASSWORD",
            "NEXTCLOUD_ADMIN_PASSWORD",
        ],
    },
}

# ============================================================================
# VARIABLE TYPE INFERENCE
# ============================================================================

TYPE_PATTERNS = {
    "url": re.compile(r"^https?://"),
    "path": re.compile(r"^/[a-zA-Z0-9/_-]+"),
    "integer": re.compile(r"^\d+$"),
    "float": re.compile(r"^\d+\.\d+$"),
    "boolean": re.compile(r"^(true|false|yes|no|1|0)$", re.IGNORECASE),
    "json": re.compile(r"^[\{|\[].*[\}|\]]$"),
    "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    "ipv4": re.compile(r"^(\d{1,3}\.){3}\d{1,3}$"),
    "ipv6": re.compile(r"^([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}$", re.IGNORECASE),
}

# ============================================================================
# VALIDATION RULES
# ============================================================================

VALIDATION_RULES = {
    "DATABASE_URL": {
        "pattern": r"^postgresql://.*:.*@.*:\d+/.*$",
        "description": "PostgreSQL connection string",
    },
    "API_KEY_.*": {
        "pattern": r"^[a-zA-Z0-9_-]{20,}$",
        "minLength": 20,
        "description": "API key format validation",
    },
    "JWT_SECRET": {
        "pattern": r"^[a-zA-Z0-9_-]{32,}$",
        "minLength": 32,
        "description": "JWT secret must be 32+ chars",
    },
    "PORT": {
        "pattern": r"^\d{2,5}$",
        "minValue": 1024,
        "maxValue": 65535,
        "description": "Valid port number",
    },
    "OLLAMA_HOST": {
        "pattern": r"^https?://[a-zA-Z0-9.-]+:\d+$",
        "description": "Ollama server URL with port",
    },
    "TRADING_DRY_RUN": {
        "pattern": r"^(true|false)$",
        "description": "Boolean flag for dry run mode",
    },
}

# ============================================================================
# OUTPUT FORMATS
# ============================================================================

OUTPUT_FORMATS = {
    "json": "Machine-readable JSON catalog",
    "markdown": "Human-readable markdown documentation",
    "csv": "Spreadsheet-compatible CSV",
    "openmetadata": "OpenMetadata standard format",
    "terraform": "Terraform variable definitions",
    "docker": "Docker .env format",
}

# ============================================================================
# DOCUMENTATION TEMPLATES
# ============================================================================

DOCUMENTATION_TEMPLATE = """
## {service_name}

### Description
{description}

### Variables
{variables_table}

### Dependencies
{dependencies}

### Critical Variables
{critical_vars}

### Examples
```
{examples}
```
"""

# ============================================================================
# EXPORT CONFIGURATION
# ============================================================================

EXPORT_CONFIG = {
    "default_format": "json",
    "include_sensitive": False,  # Never export secret values
    "include_defaults": True,
    "include_examples": True,
    "pretty_print": True,
    "output_dir": ".variables-catalog",
}
