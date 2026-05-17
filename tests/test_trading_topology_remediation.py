from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.audit_trading_topology import parse_systemctl_units
from tools.remediate_trading_topology import build_remediation_commands, choose_single_units


def test_choose_single_units_prefers_conservative_and_non_legacy_exporter() -> None:
    raw = """
crypto-agent@BTC_USDT_aggressive.service loaded active running Crypto Trading Agent - BTC_USDT_aggressive
crypto-agent@BTC_USDT_conservative.service loaded active running Crypto Trading Agent - BTC_USDT_conservative
autocoinbot-exporter.service loaded active running Legacy BTC exporter
crypto-exporter@BTC_USDT_conservative.service loaded active running BTC exporter conservative
crypto-exporter@BTC_USDT_aggressive.service loaded active running BTC exporter aggressive
"""
    units = parse_systemctl_units(raw)
    decisions = choose_single_units(
        units,
        preferred_profile="conservative",
        prefer_legacy_exporter=False,
    )

    by_role = {decision.role: decision for decision in decisions}
    assert by_role["agent"].keep_unit == "crypto-agent@BTC_USDT_conservative.service"
    assert "crypto-agent@BTC_USDT_aggressive.service" in by_role["agent"].disable_units

    assert by_role["exporter"].keep_unit == "crypto-exporter@BTC_USDT_conservative.service"
    assert "autocoinbot-exporter.service" in by_role["exporter"].disable_units
    assert "crypto-exporter@BTC_USDT_aggressive.service" in by_role["exporter"].disable_units


def test_build_remediation_commands_emits_stop_disable_pairs() -> None:
    raw = """
crypto-agent@BTC_USDT_aggressive.service loaded active running Crypto Trading Agent - BTC_USDT_aggressive
crypto-agent@BTC_USDT_conservative.service loaded active running Crypto Trading Agent - BTC_USDT_conservative
"""
    decisions = choose_single_units(
        parse_systemctl_units(raw),
        preferred_profile="conservative",
        prefer_legacy_exporter=False,
    )
    commands = build_remediation_commands(decisions)

    assert commands[0] == "sudo systemctl stop crypto-agent@BTC_USDT_aggressive.service"
    assert commands[1] == "sudo systemctl disable crypto-agent@BTC_USDT_aggressive.service"
    assert commands[-1] == "sudo systemctl daemon-reload"
