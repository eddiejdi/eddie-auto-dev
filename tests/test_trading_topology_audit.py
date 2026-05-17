from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.audit_trading_topology import (
    build_report,
    parse_listeners,
    parse_systemctl_units,
)


def test_parse_systemctl_units_normalizes_profiles_and_legacy() -> None:
    raw = """
crypto-agent@BTC_USDT_conservative.service loaded active running Crypto Trading Agent - BTC_USDT_conservative
crypto-agent@BTC-USDT-aggressive.service loaded active running Crypto Trading Agent - BTC-USDT-aggressive
autocoinbot-exporter.service loaded active running Legacy BTC exporter
"""
    records = parse_systemctl_units(raw)

    assert records[0].coin == "BTC-USDT"
    assert records[0].profile == "conservative"
    assert records[0].naming_variant == "underscore"

    assert records[1].coin == "BTC-USDT"
    assert records[1].profile == "aggressive"
    assert records[1].naming_variant == "hyphen"

    assert records[2].coin == "BTC-USDT"
    assert records[2].profile == "default"
    assert records[2].is_legacy is True


def test_build_report_flags_duplicates_per_coin() -> None:
    units_raw = """
crypto-agent@BTC_USDT_conservative.service loaded active running Crypto Trading Agent - BTC_USDT_conservative
crypto-agent@BTC_USDT_aggressive.service loaded active running Crypto Trading Agent - BTC_USDT_aggressive
crypto-exporter@BTC_USDT_conservative.service loaded active running BTC exporter conservative
autocoinbot-exporter.service loaded active running Legacy BTC exporter
crypto-agent@ETH_USDT_conservative.service loaded inactive dead ETH conservative
"""
    listeners_raw = """
LISTEN 0      128          0.0.0.0:9092      0.0.0.0:*    users:(("python3",pid=100,fd=7))
LISTEN 0      128          0.0.0.0:9100      0.0.0.0:*    users:(("node_exporter",pid=200,fd=3))
"""
    report = build_report(parse_systemctl_units(units_raw), parse_listeners(listeners_raw))

    assert "BTC-USDT" in report["duplicate_agents"]
    assert "BTC-USDT" in report["duplicate_exporters"]
    assert "ETH-USDT" in report["missing_expected_agents"]
    assert report["listeners"][0]["port"] == 9092
    assert report["listeners"][1]["process"].startswith('users:(("node_exporter"')
