"""Convívio aggressive+shadow na mesma sub KuCoin (helpers isolados)."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "btc_trading_agent" / "trading_agent.py"
SRC = AGENT.read_text(encoding="utf-8")


def test_resolve_dry_run_allows_live_shadow_in_source():
    """Garante que shadow NÃO é forçado dry-run no resolver."""
    # Não deve existir early-return dry-run só por profile==shadow
    assert 'if profile == "shadow":\n        return True' not in SRC
    # Deve documentar que shadow pode ser live
    assert "capital_share" in SRC or "shared" in SRC.lower()


def test_clamp_and_capital_share_helpers_exist():
    assert "def _clamp_sell_size_to_shared_inventory" in SRC
    assert "def _peer_open_base_on_shared_sub" in SRC
    assert "def _config_capital_share" in SRC
    assert "def _live_profiles_for_sub" in SRC
    assert "multi_share" in SRC
    assert "primary" in SRC


def test_shadow_and_aggressive_configs_share_sub():
    import json

    shadow = json.loads((ROOT / "btc_trading_agent" / "config_BTC_USDT_shadow.json").read_text())
    aggr = json.loads((ROOT / "btc_trading_agent" / "config_BTC_USDT_aggressive.json").read_text())
    assert shadow.get("dry_run") is False
    assert shadow.get("live_mode") is True
    assert shadow.get("kucoin_subaccount_name") == "BTCAgressive"
    assert aggr.get("kucoin_subaccount_name") == "BTCAgressive"
    assert abs(float(shadow.get("capital_share")) + float(aggr.get("capital_share")) - 1.0) < 1e-9
    assert float(shadow["capital_share"]) < float(aggr["capital_share"])


def test_clamp_logic_unit():
    """Lógica de clamp sem importar trading_agent (evita deps pesadas)."""

    def clamp(size, real, peers, own):
        mine_room = max(0.0, real - peers)
        return max(0.0, min(size, mine_room, own if own > 0 else size))

    assert abs(clamp(0.0008, 0.001, 0.0005, 0.0008) - 0.0005) < 1e-12
    assert abs(clamp(0.0003, 0.001, 0.0005, 0.0008) - 0.0003) < 1e-12
    assert clamp(0.0008, 0.0004, 0.0005, 0.0008) == 0.0
