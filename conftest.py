import re
import pathlib
import pytest

# Heuristics to detect tests that require infra or external libs.
PATTERNS_INTEGRATION = [
    r"localhost[:\\/0-9]*8503",
    r"127\.0\.0\.1[:\\/0-9]*8503",
    r"192\.168\.",
    r"/home/homelab",
    r"/home/eddie",
    r"interceptor/conversations",
    r"requests\.get\(",
    r"requests\.post\(",
    r"subprocess\.run\(",
    r"wsl",
]

PATTERNS_EXTERNAL = [
    r"import\s+tinytuya",
    r"import\s+tuya_iot",
    r"import\s+paramiko",
    r"import\s+chromadb",
    r"from\s+google\.oauth2",
    r"import\s+playwright",
]


def _file_contains_any(path: pathlib.Path, patterns):
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return False
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def pytest_collection_modifyitems(config, items):
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

        # Optional: annotate reason in item's user_properties for debugging
        if marked:
            item.user_properties.append(("auto_marked", True))