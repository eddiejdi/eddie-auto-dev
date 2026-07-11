from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_DIR))

import secrets_loader

secrets_loader.get_telegram_token = lambda: "test-token"  # type: ignore[method-assign]

_SPEC = importlib.util.spec_from_file_location(
    "daily_agenda_approval",
    TOOLS_DIR / "daily_agenda_approval.py",
)
assert _SPEC is not None and _SPEC.loader is not None
approval = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = approval
_SPEC.loader.exec_module(approval)


def test_approval_keyboard_contains_actions() -> None:
    keyboard = approval.approval_keyboard("2026-07-09")
    row = keyboard["inline_keyboard"][0]
    callbacks = {btn["callback_data"] for btn in row}
    assert "dag:A:2026-07-09" in callbacks
    assert "dag:R:2026-07-09" in callbacks


def test_parse_callback_data() -> None:
    assert approval._parse_callback_data("dag:A:2026-07-10") == ("approved", "2026-07-10")
    assert approval._parse_callback_data("dag:R:2026-07-10") == ("regenerate", "2026-07-10")
    assert approval._parse_callback_data("A:intent") is None


def test_save_and_load_state(tmp_path: Path) -> None:
    path = tmp_path / "approval_pending.json"
    state = approval.ApprovalState(
        date_str="2026-07-09",
        status="waiting",
        attempt=1,
        deep_search=False,
        message_id=10,
        audio_message_id=11,
        created_at="2026-07-09T07:00:00",
    )
    approval.save_state(state, path=path)
    loaded = approval.load_state(path=path)
    assert loaded is not None
    assert loaded.date_str == "2026-07-09"
    assert loaded.status == "waiting"


def test_handle_telegram_callback_updates_state(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "approval_pending.json"
    approval.save_state(
        approval.ApprovalState(
            date_str="2026-07-09",
            status="waiting",
            attempt=1,
            deep_search=False,
            message_id=10,
            audio_message_id=11,
            created_at="2026-07-09T07:00:00",
        ),
        path=path,
    )
    monkeypatch.setattr(approval, "APPROVAL_FILE", path)
    monkeypatch.setattr(approval, "_telegram_api", lambda *args, **kwargs: {})

    handled = approval.handle_telegram_callback(
        {
            "id": "cb1",
            "data": "dag:A:2026-07-09",
            "from": {"username": "eden"},
            "message": {"message_id": 10, "chat": {"id": 123}},
        }
    )
    assert handled is True
    updated = approval.load_state(path=path)
    assert updated is not None
    assert updated.status == "approved"
    assert updated.decided_by == "eden"


def test_wait_for_decision_reads_saved_state(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "approval_pending.json"
    path.write_text(
        json.dumps(
            {
                "date_str": "2026-07-09",
                "status": "approved",
                "attempt": 1,
                "deep_search": False,
                "message_id": 1,
                "audio_message_id": 2,
                "created_at": "2026-07-09T07:00:00",
                "decided_at": "2026-07-09T07:05:00",
                "decided_by": "eden",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(approval, "APPROVAL_FILE", path)
    decision = approval.wait_for_decision(
        date_str="2026-07-09",
        timeout_minutes=0,
        poll_telegram=False,
    )
    assert decision == "approved"