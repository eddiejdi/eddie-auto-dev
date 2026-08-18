"""RealDictRow não aceita r[0] — o botão Aprovar caía em 'Intent não encontrado'."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parent.parent
    / "specialized_agents"
    / "approval_gateway.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("approval_gateway_resolve_test", _PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_row_intent_id_from_dict() -> None:
    gw = _load()
    assert gw._row_intent_id({"intent_id": "intent-20260813-120746-1a8795"}) == (
        "intent-20260813-120746-1a8795"
    )


def test_row_intent_id_from_tuple() -> None:
    gw = _load()
    assert gw._row_intent_id(("intent-abc",)) == "intent-abc"


def test_row_intent_id_none() -> None:
    gw = _load()
    assert gw._row_intent_id(None) is None
    assert gw._row_intent_id({}) is None
