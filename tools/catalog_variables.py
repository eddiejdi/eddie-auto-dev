#!/usr/bin/env python3
"""
Variables Catalog Generator
Scans homelab environment for all variable definitions across multiple sources.

Sources scanned:
- .env files
- docker-compose.yml files
- systemd service files
- Python configuration files
- YAML config files
- Environment variable exports in scripts
"""

import os
import re
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any, Tuple
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class VariablesCatalog:
    """Main catalog generator."""
    
    def __init__(self, root_path: str = "/workspace/eddie-auto-dev"):
        self.root = Path(root_path)
        self.catalog = {
            "catalogVersion": "1.0.0",
            "generatedAt": datetime.now().isoformat(),
            "environment": "production",
            "categories": defaultdict(dict),
            "metadata": {
                "totalVariables": 0,
                "sourceFiles": [],
                "serviceCount": 0
            }
        }
        self.variables_found: Set[str] = set()
        self.sources_scanned: List[Tuple[str, str]] = []
        
    def scan_env_files(self) -> Dict[str, Any]:
        """Scan .env and .env.example files."""
        logger.info("📋 Scanning .env files...")
        env_vars = {}
        
        patterns = [".env", ".env.*", "*.env"]
        for pattern in patterns:
            for env_file in self.root.rglob(pattern):
                # Skip node_modules, venv, .git
                if any(skip in str(env_file) for skip in ['node_modules', '.venv', '.git', '__pycache__']):
                    continue
                    
                self._parse_env_file(env_file, env_vars)
                
        return env_vars
    
    def _parse_env_file(self, filepath: Path, env_vars: Dict):
        """Parse a single .env file."""
        logger.info(f"  └─ {filepath.relative_to(self.root)}")
        self.sources_scanned.append((str(filepath.relative_to(self.root)), "env"))
        
        try:
            with open(filepath, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE
                    match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line, re.IGNORECASE)
                    if match:
                        key, value = match.groups()
                        
                        if key not in env_vars:
                            env_vars[key] = {
                                "name": key,
                                "type": self._infer_type(value),
                                "source": ".env",
                                "value": value if not self._is_sensitive(key, value) else "***REDACTED***",
                                "locations": []
                            }
                        
                        env_vars[key]["locations"].append({
                            "file": str(filepath.relative_to(self.root)),
                            "line": line_num
                        })
                        self.variables_found.add(key)
        except Exception as e:
            logger.error(f"    Error parsing {filepath}: {e}")
    
    def scan_docker_compose(self) -> Dict[str, Any]:
        """Scan docker-compose.yml files."""
        logger.info("🐳 Scanning docker-compose files...")
        docker_vars = {}
        
        for compose_file in self.root.rglob("docker-compose*.yml"):
            if '.git' in str(compose_file):
                continue
                
            logger.info(f"  └─ {compose_file.relative_to(self.root)}")
            self.sources_scanned.append((str(compose_file.relative_to(self.root)), "docker-compose"))
            
            try:
                with open(compose_file, 'r') as f:
                    content = yaml.safe_load(f)
                    if not content:
                        continue
                    
                    # Extract from 'services' section
                    if 'services' in content:
                        for service_name, service_config in content['services'].items():
                            if isinstance(service_config, dict) and 'environment' in service_config:
                                env_list = service_config['environment']
                                
                                if isinstance(env_list, dict):
                                    for key, value in env_list.items():
                                        self._add_variable(docker_vars, key, value, 
                                                         "docker-compose", service_name)
                                elif isinstance(env_list, list):
                                    for item in env_list:
                                        if '=' in item:
                                            key, value = item.split('=', 1)
                                            self._add_variable(docker_vars, key, value,
                                                             "docker-compose", service_name)
            except Exception as e:
                logger.error(f"    Error parsing {compose_file}: {e}")
        
        return docker_vars
    
    def scan_systemd_services(self) -> Dict[str, Any]:
        """Scan systemd service files."""
        logger.info("⚙️  Scanning systemd services...")
        systemd_vars = {}
        
        systemd_path = self.root / "systemd"
        if not systemd_path.exists():
            logger.info("  └─ No systemd directory found")
            return systemd_vars
        
        for service_file in systemd_path.glob("*.service"):
            logger.info(f"  └─ {service_file.relative_to(self.root)}")
            self.sources_scanned.append((str(service_file.relative_to(self.root)), "systemd"))
            
            try:
                with open(service_file, 'r') as f:
                    service_name = service_file.stem
                    for line in f:
                        # Look for Environment= and EnvironmentFile=
                        if line.strip().startswith('Environment='):
                            env_str = line.split('Environment=', 1)[1].strip()
                            if '=' in env_str:
                                key, value = env_str.split('=', 1)
                                key = key.strip('"\'')
                                value = value.strip('"\'')
                                self._add_variable(systemd_vars, key, value, 
                                                 "systemd", service_name)
                        elif line.strip().startswith('EnvironmentFile='):
                            env_file = line.split('EnvironmentFile=', 1)[1].strip()
                            env_file_path = self.root / env_file.lstrip('-')
                            if env_file_path.exists():
                                self._parse_env_file(env_file_path, systemd_vars)
            except Exception as e:
                logger.error(f"    Error parsing {service_file}: {e}")
        
        return systemd_vars
    
    def scan_python_configs(self) -> Dict[str, Any]:
        """Scan Python configuration files and code."""
        logger.info("🐍 Scanning Python configs...")
        python_vars = {}
        
        # Look for config.py, settings.py, etc
        config_files = list(self.root.rglob("*config*.py")) + \
                      list(self.root.rglob("*settings*.py"))
        
        for config_file in config_files:
            if any(skip in str(config_file) for skip in ['.venv', '__pycache__', '.git']):
                continue
            
            logger.info(f"  └─ {config_file.relative_to(self.root)}")
            self.sources_scanned.append((str(config_file.relative_to(self.root)), "python"))
            
            try:
                with open(config_file, 'r') as f:
                    content = f.read()
                    
                    # Look for os.getenv() and os.environ patterns
                    patterns = [
                        r"os\.getenv\(['\"]([A-Z_][A-Z0-9_]*)['\"]",
                        r"os\.environ\[['\"]([A-Z_][A-Z0-9_]*)['\"]",
                        r"os\.environ\.get\(['\"]([A-Z_][A-Z0-9_]*)['\"]",
                    ]
                    
                    for pattern in patterns:
                        for match in re.finditer(pattern, content):
                            key = match.group(1)
                            self._add_variable(python_vars, key, None, 
                                             "python-config", 
                                             config_file.stem)
            except Exception as e:
                logger.error(f"    Error scanning {config_file}: {e}")
        
        return python_vars
    
    def scan_yaml_configs(self) -> Dict[str, Any]:
        """Scan YAML configuration files."""
        logger.info("📝 Scanning YAML configs...")
        yaml_vars = {}
        
        yaml_files = list(self.root.rglob("*.yml")) + list(self.root.rglob("*.yaml"))
        for yaml_file in yaml_files:
            if any(skip in str(yaml_file) for skip in ['.git', 'docker-compose']):
                continue
            
            logger.info(f"  └─ {yaml_file.relative_to(self.root)}")
            self.sources_scanned.append((str(yaml_file.relative_to(self.root)), "yaml"))
            
            try:
                with open(yaml_file, 'r') as f:
                    content = yaml.safe_load(f)
                    self._extract_vars_from_dict(content, yaml_vars, yaml_file.stem)
            except Exception as e:
                logger.error(f"    Error parsing {yaml_file}: {e}")
        
        return yaml_vars
    
    def _extract_vars_from_dict(self, obj: Any, vars_dict: Dict, context: str, prefix: str = ""):
        """Recursively extract variables from dictionary."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_key = f"{prefix}_{key}".upper() if prefix else key.upper()
                
                if isinstance(value, (str, int, float, bool)):
                    self._add_variable(vars_dict, full_key, str(value), "yaml", context)
                elif isinstance(value, dict):
                    self._extract_vars_from_dict(value, vars_dict, context, full_key)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            self._extract_vars_from_dict(item, vars_dict, context, f"{full_key}_{i}")
    
    def _add_variable(self, vars_dict: Dict, key: str, value: Any, source: str, context: str):
        """Add variable to dictionary."""
        if key not in vars_dict:
            vars_dict[key] = {
                "name": key,
                "type": self._infer_type(str(value)) if value else "string",
                "source": source,
                "value": value if not self._is_sensitive(key, value) else "***REDACTED***",
                "contexts": set()
            }
        
        if hasattr(vars_dict[key]['contexts'], 'add'):
            vars_dict[key]['contexts'].add(context)
        self.variables_found.add(key)
    
    def _infer_type(self, value: str) -> str:
        """Infer variable type from value."""
        if value is None or value == "":
            return "string"
        
        value_lower = str(value).lower().strip()
        if value_lower in ('true', 'false', 'yes', 'no', '1', '0'):
            return "boolean"
        # Check for URLs (including with credentials like postgresql://user:pass@host)
        if value_lower.startswith('http://') or value_lower.startswith('https://') or \
           value_lower.startswith('postgresql://') or value_lower.startswith('mysql://') or \
           value_lower.startswith('mongodb://') or value_lower.startswith('redis://'):
            return "url"
        if value.isdigit():
            return "integer"
        try:
            float(value)
            return "float"
        except ValueError:
            pass
        if value.startswith('{') or value.startswith('['):
            return "json"
        if value.startswith('/'):
            return "path"
        
        return "string"
    
    def _is_sensitive(self, key: str, value: str = "") -> bool:
        """Check if a variable name or value suggests it contains sensitive data."""
        sensitive_keywords = [
            'secret', 'password', 'token', 'key', 'api_key', 'apikey',
            'auth', 'credential', 'private', 'oauth', 'jwt', 'bearer',
            'access_token', 'refresh_token', 'webhook', 'seed',
            'dsn', 'connection_string', 'conn_str',
        ]

        key_lower = key.lower()
        if any(keyword in key_lower for keyword in sensitive_keywords):
            return True

        # DATABASE_URL/URI-style names don't match the keyword list, but their
        # value often embeds a credential (scheme://user:pass@host) — catch by shape.
        if value and self._DSN_CRED_RE.search(str(value)):
            return True
        return False

    _DSN_CRED_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")
    
    def categorize_variables(self, all_vars: Dict[str, Any]):
        """Categorize variables into semantic groups."""
        logger.info("\n🏷️  Categorizing variables...")
        
        # Order matters: more specific categories first
        categories = {
            "trading": r"(TRADING|EXCHANGE|MT5|CRYPTO|BTC|ETH|COIN|STRATEGY|POSITION|ORDER)",
            "authentication": r"(AUTH|TOKEN|SECRET|PASSWORD|KEY|APIKEY|JWT|BEARER|OAUTH)",
            "database": r"(DATABASE|DB_|POSTGRES|MYSQL|REDIS|MONGODB|ELASTIC)",
            "infrastructure": r"(DOCKER|KUBERNETES|NETWORK|STORAGE|VOLUME|MOUNT)",
            "integrations": r"(SLACK|TELEGRAM|GITHUB|GITLAB|WEBHOOK|GOOGLE|AWS)",
            "monitoring": r"(MONITORING|LOGGING|GRAFANA|PROMETHEUS|SENTRY|ALERT)",
            "services": r"(API|SERVICE|HOST|PORT|URL|ENDPOINT)",
        }
        
        for var_name, var_data in all_vars.items():
            categorized = False
            for category, pattern in categories.items():
                if re.search(pattern, var_name, re.IGNORECASE):
                    if var_name not in self.catalog["categories"][category]:
                        var_data['contexts'] = list(var_data.get('contexts', set()))
                        self.catalog["categories"][category][var_name] = var_data
                        categorized = True
                    break
            
            if not categorized:
                if var_name not in self.catalog["categories"]["services"]:
                    var_data['contexts'] = list(var_data.get('contexts', set()))
                    self.catalog["categories"]["services"][var_name] = var_data
    
    def generate_catalog(self) -> Dict[str, Any]:
        """Generate complete variables catalog."""
        logger.info("\n" + "="*70)
        logger.info("🔍 HOMELAB VARIABLES CATALOG SCANNER")
        logger.info("="*70 + "\n")
        
        # Scan all sources
        env_vars = self.scan_env_files()
        docker_vars = self.scan_docker_compose()
        systemd_vars = self.scan_systemd_services()
        python_vars = self.scan_python_configs()
        yaml_vars = self.scan_yaml_configs()
        
        # Merge all variables
        all_vars = {**env_vars, **docker_vars, **systemd_vars, **python_vars, **yaml_vars}
        
        # Categorize
        self.categorize_variables(all_vars)
        
        # Update metadata
        self.catalog["metadata"]["totalVariables"] = len(self.variables_found)
        self.catalog["metadata"]["sourceFiles"] = [s[0] for s in self.sources_scanned]
        
        logger.info("\n" + "="*70)
        logger.info("📊 CATALOG SUMMARY")
        logger.info("="*70)
        logger.info(f"✅ Total variables found: {len(self.variables_found)}")
        logger.info(f"✅ Source files scanned: {len(self.sources_scanned)}")
        
        for category, vars_in_cat in self.catalog["categories"].items():
            if vars_in_cat:
                logger.info(f"  • {category.capitalize()}: {len(vars_in_cat)} variables")
        
        logger.info("="*70 + "\n")
        
        return self.catalog
    
    def save_catalog(self, output_file: str = None):
        """Save catalog to JSON file."""
        if output_file is None:
            output_file = self.root / ".variables-catalog" / "catalog.json"
        else:
            output_file = Path(output_file)
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(self.catalog, f, indent=2, default=str)
        
        logger.info(f"💾 Catalog saved to: {output_file}")
        return output_file


def main():
    """Main entry point."""
    catalog = VariablesCatalog()
    catalog.generate_catalog()
    catalog.save_catalog()


if __name__ == "__main__":
    main()
