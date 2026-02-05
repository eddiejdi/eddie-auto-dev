#!/usr/bin/env python3
"""Repo-level pytest configuration: skip heavy integration/external tests by default.

This file contains heuristics used during local and CI test collection to avoid
import-time failures for tests that require local services or external libs.

Set RUN_INTEGRATION=1 to run integration tests, or RUN_ALL_TESTS=1 to collect
top-level tests in the repository root.
"""

import os
import re
import pathlib
import pytest
import sys

# Prevent pytest from discovering tests inside virtualenv/site-packages
orig_sys_path = list(sys.path)
sys.path[:] = [p for p in sys.path if p and 'site-packages' not in p and '.venv' not in p and 'venv' not in p]


# Files we know are heavy/integration-focused and should be skipped by default
SKIP_PATTERNS = [
    'test_ai_training.py',
    'test_ai_final.py',
    'test_rpa_selenium.py',
    'test_webui_install.py',
    'test_endpoints_final.py',
    'test_interceptor.py',
    'test_rpa_scraping.py',
    'test_selenium_endpoints.py',
    'test_github_agent.py',
    'test_gmail_integration.py',
    'smartlife_integration',
    'DEV_20260109164710',
    'DEV_20260109172705',
    'DEV_20260109174028',
    'DEV_20260109192009',
    'test_site_selenium.py',
    'site_selenium',
    'training_data',
    'test_rag_search.py',
    'tests/test_site_selenium.py',
]
# Additional known-integration tests that should be skipped by default
SKIP_PATTERNS += [
    'test_interceptor_db.py',
    'test_models.py',
    'test_api_integration.py',
    'test_api_generate.py',
    'test_remote_orchestrator.py',
    'test_printer_function.py',
    'test_restrictions.py',
    'test_github_flow.py',
]


# Heuristics to detect tests that require infra or external libs.
PATTERNS_INTEGRATION = [
    r"localhost[:\\/0-9]*8503",
    r"127\\.0\\.0\\.1[:\\/0-9]*8503",
    r"192\\.168\\.",
    r"/home/homelab",
    r"/home/eddie",
    r"interceptor/conversations",
    r"requests\\.get\\(",
    r"requests\\.post\\(",
    r"subprocess\\.run\\(",
    r"wsl",
]

PATTERNS_EXTERNAL = [
    r"import\s+tinytuya",
    r"import\s+tuya_iot",
    r"import\s+paramiko",
    r"import\s+chromadb",
    r"from\s+google\\.oauth2",
    r"import\s+playwright",
]

IGNORE_PATTERNS = [
    r"GITHUB_TOKEN not definido",
    r"sys\\.exit\(1\)",
    r"os\\.chdir\('/home/homelab'",
    r"os\\.chdir\('/home/eddie'",
    r"wsl",
]


def _file_contains_any(path: pathlib.Path, patterns):
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return False
    for p in patterns:
        try:
            if re.search(p, text):
                return True
        except re.error:
            # ignore invalid/unterminated regex patterns
            continue
    return False


def pytest_collection_modifyitems(config, items):
    # Skip known heavy tests unless explicitly enabled
    if os.getenv('RUN_INTEGRATION') != '1':
        skip = pytest.mark.skip(reason="Integration/external test skipped by CI policy. Set RUN_INTEGRATION=1 to run.")
        for item in items:
            path = str(item.fspath)
            nodeid = item.nodeid
            if any(p in path or p in nodeid for p in SKIP_PATTERNS):
                item.add_marker(skip)

    # Auto-mark tests that appear to be integration/external for clarity
    for item in items:
        try:
            path = pathlib.Path(item.fspath)
        except Exception:
            continue

        marked = False
        if _file_contains_any(path, PATTERNS_EXTERNAL):
            item.add_marker(pytest.mark.external)
            marked = True
        if _file_contains_any(path, PATTERNS_INTEGRATION):
            item.add_marker(pytest.mark.integration)
            marked = True

        if marked:
            item.user_properties.append(("auto_marked", True))


def pytest_ignore_collect(collection_path, config):
    """Ignore collecting test files that match ignore patterns to avoid import-time side effects."""
    try:
        p = pathlib.Path(collection_path)
    except Exception:
        try:
            p = pathlib.Path(str(collection_path))
        except Exception:
            return False

    # Avoid collecting tests that live inside virtualenvs or site-packages
    parts = [ppart.lower() for ppart in p.parts]
    for part in parts:
        if part.startswith('.venv') or 'site-packages' in part or part.startswith('venv'):
            return True

    try:
        text = p.read_text(errors="ignore")
    except Exception:
        return False

    for pat in IGNORE_PATTERNS:
        if re.search(pat, text):
            return True

    # If test imports clearly external libs, ignore collection to avoid failures
    for pat in PATTERNS_EXTERNAL:
        if re.search(pat, text):
            return True

    # Also ignore by explicit SKIP_PATTERNS (path or filename match)
    try:
        for pat in SKIP_PATTERNS:
            if pat and (pat in str(p) or pat == p.name):
                return True
    except Exception:
        pass

    # Ignore top-level tests (in repo root) by default to avoid import-time side effects.
    # Set RUN_ALL_TESTS=1 to override and collect everything.
    try:
        repo_root = pathlib.Path.cwd()
        if p.is_file() and p.parent.resolve() == repo_root.resolve():
            name = p.name
            if name.startswith("test_") or name.endswith("_test.py"):
                if os.environ.get("RUN_ALL_TESTS", "0") != "1":
                    return True
    except Exception:
        pass

    return False
