#!/usr/bin/env python3
"""Testes do detector global no_silent_failure + incident_notify."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.hooks.no_silent_failure import scan_python, scan_shell


def test_except_pass_flagged() -> None:
    findings = scan_python(
        "demo.py",
        "try:\n    x()\nexcept Exception:\n    pass\n",
    )
    assert any(f.kind == "except-pass" for f in findings)


def test_except_return_none_silent_flagged() -> None:
    findings = scan_python(
        "demo.py",
        "try:\n    x()\nexcept Exception:\n    return None\n",
    )
    assert any("return-empty" in f.kind for f in findings)


def test_except_with_logger_ok() -> None:
    findings = scan_python(
        "demo.py",
        "try:\n    x()\nexcept Exception as e:\n    logger.error('fail %s', e)\n    return None\n",
    )
    assert findings == []


def test_silent_ok_escape() -> None:
    findings = scan_python(
        "demo.py",
        "try:\n    x()\nexcept Exception:\n    pass  # silent-ok\n",
    )
    assert findings == []


def test_shell_wiki_swallow_flagged() -> None:
    findings = scan_shell(
        "hook.sh",
        'python3 tools/hooks/wiki_sync.py "$f" >/dev/null 2>&1 || true\n',
    )
    assert findings


def test_incident_notify_writes_log(tmp_path, monkeypatch) -> None:
    from tools.hooks import incident_notify as mod

    log = tmp_path / "hook_incidents.log"
    art = tmp_path / "arts"
    monkeypatch.setattr(mod, "LOG_FILE", log)
    monkeypatch.setattr(mod, "ARTIFACT_DIR", art)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    payload = mod.emit_incident("unit-test", "hello", severity="info", details="d")
    assert payload["summary"] == "hello"
    assert log.exists()
    assert "hello" in log.read_text()
    assert list(art.glob("incident_*.json"))
