#!/usr/bin/env python3
"""
Configuration exports for Variables Catalog
This file re-exports configurations from .variables-catalog/config.py
"""

import sys
from pathlib import Path

config_path = Path(__file__).parent / ".." / ".variables-catalog" / "config.py"
if config_path.exists():
    spec = __import__('importlib.util').util.spec_from_file_location("_config", config_path)
    config_module = __import__('importlib.util').util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    TYPE_PATTERNS = getattr(config_module, 'TYPE_PATTERNS', {})
    SENSITIVE_KEYWORDS = getattr(config_module, 'SENSITIVE_KEYWORDS', [])
    SERVICES = getattr(config_module, 'SERVICES', {})
else:
    # Fallback defaults
    TYPE_PATTERNS = {}
    SENSITIVE_KEYWORDS = ['secret', 'password', 'token', 'key']
    SERVICES = {}
