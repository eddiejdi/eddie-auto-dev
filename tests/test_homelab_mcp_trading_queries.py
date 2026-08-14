"""Queries de trading do MCP: created_at derivado de timestamp e profile vivo."""
from __future__ import annotations

import re
from pathlib import Path

SRC = (
    Path(__file__).resolve().parent.parent / "scripts" / "homelab_mcp_server.py"
).read_text(encoding="utf-8")
_TS_AS_CREATED = "to_timestamp(timestamp) AS created_at"


def _fn_source(name: str) -> str:
    match = re.search(
        rf"def {name}\(.*?(?=\n@mcp\.tool\(\)|\ndef [a-z_]+\()",
        SRC,
        flags=re.S,
    )
    assert match is not None, f"função {name} não encontrada"
    return match.group(0)


def test_decisions_and_market_state_map_timestamp_to_created_at() -> None:
    for name in ("trading_decisions", "trading_market_state"):
        body = _fn_source(name)
        assert _TS_AS_CREATED in body
        assert "volume, created_at" not in body
        assert "servidor, created_at" not in body


def test_trading_summary_default_profile_is_conservative() -> None:
    assert 'def trading_summary(symbol: str = "BTC-USDT", profile: str = "conservative")' in SRC
    for name in ("trading_ai_plan", "trading_ai_controls", "trading_ai_window"):
        body = _fn_source(name)
        assert 'profile: str = "conservative"' in body
        assert 'profile: str = "default"' not in body
