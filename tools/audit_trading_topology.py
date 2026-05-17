#!/usr/bin/env python3
"""Audit trading topology on the homelab host.

Focus:
- detect active duplicate agent/exporter instances per coin;
- highlight legacy/default units mixed with templated units;
- list listeners on known trading ports;
- support a "single active instance per coin" policy.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Iterable

KNOWN_COINS = (
    "BTC-USDT",
    "ETH-USDT",
    "XRP-USDT",
    "SOL-USDT",
    "DOGE-USDT",
    "ADA-USDT",
)
KNOWN_PROFILES = {"conservative", "aggressive", "default"}
UNIT_PATTERNS = (
    "crypto-agent@*",
    "crypto-exporter@*",
    "autocoinbot-exporter*",
    "btc-trading-agent.service",
)
PORT_PATTERN = (
    r":(8510|8511|8512|8513|8514|8515|8516|8517|8518|8519|8520|8521|"
    r"9092|9093|9094|9095|9096|9097|9098|9100|9101|9102|9103|9104|9105|"
    r"9106|9107|9108|9109|9110|9111)\b"
)


@dataclass(frozen=True)
class UnitRecord:
    unit_name: str
    role: str
    coin: str | None
    profile: str | None
    active_state: str
    sub_state: str
    description: str
    instance_slug: str | None
    is_legacy: bool
    naming_variant: str | None


@dataclass(frozen=True)
class ListenerRecord:
    port: int
    process: str
    raw: str


def _run_ssh(user: str, host: str, command: str) -> str:
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", f"{user}@{host}", command],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ssh exited with {proc.returncode}")
    return proc.stdout


def _extract_instance_slug(unit_name: str) -> str | None:
    if "@" in unit_name:
        return unit_name.split("@", 1)[1].removesuffix(".service")
    return None


def _normalize_coin_and_profile(instance_slug: str | None, unit_name: str) -> tuple[str | None, str | None]:
    if instance_slug:
        tokens = [token for token in re.split(r"[_-]+", instance_slug) if token]
        if not tokens:
            return None, None
        profile = None
        if tokens[-1].lower() in KNOWN_PROFILES:
            profile = tokens.pop().lower()
        if not tokens:
            return None, profile
        return "-".join(token.upper() for token in tokens), profile or "default"

    if unit_name in {"autocoinbot-exporter.service", "btc-trading-agent.service"}:
        return "BTC-USDT", "default"
    return None, None


def _infer_role(unit_name: str) -> str | None:
    if unit_name.startswith("crypto-agent@") or unit_name == "btc-trading-agent.service":
        return "agent"
    if unit_name.startswith("crypto-exporter@") or unit_name.startswith("autocoinbot-exporter"):
        return "exporter"
    return None


def _naming_variant(instance_slug: str | None) -> str | None:
    if not instance_slug:
        return None
    if "_" in instance_slug:
        return "underscore"
    if "-" in instance_slug:
        return "hyphen"
    return "plain"


def parse_systemctl_units(raw: str) -> list[UnitRecord]:
    records: list[UnitRecord] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit_name, _load, active_state, sub_state = parts[:4]
        description = parts[4] if len(parts) == 5 else ""
        role = _infer_role(unit_name)
        if role is None:
            continue
        slug = _extract_instance_slug(unit_name)
        coin, profile = _normalize_coin_and_profile(slug, unit_name)
        records.append(
            UnitRecord(
                unit_name=unit_name,
                role=role,
                coin=coin,
                profile=profile,
                active_state=active_state,
                sub_state=sub_state,
                description=description,
                instance_slug=slug,
                is_legacy="@" not in unit_name,
                naming_variant=_naming_variant(slug),
            )
        )
    return records


def parse_listeners(raw: str) -> list[ListenerRecord]:
    listeners: list[ListenerRecord] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        local_addr = parts[3]
        process = parts[-1]
        match = re.search(r":(\d+)$", local_addr)
        if not match:
            continue
        listeners.append(
            ListenerRecord(
                port=int(match.group(1)),
                process=process,
                raw=line,
            )
        )
    return listeners


def _group_active_by_coin(records: Iterable[UnitRecord], role: str) -> dict[str, list[UnitRecord]]:
    grouped: dict[str, list[UnitRecord]] = {}
    for record in records:
        if record.role != role or record.active_state != "active" or not record.coin:
            continue
        grouped.setdefault(record.coin, []).append(record)
    return grouped


def _duplicates(grouped: dict[str, list[UnitRecord]]) -> dict[str, list[UnitRecord]]:
    return {coin: items for coin, items in grouped.items() if len(items) > 1}


def _missing_expected(grouped: dict[str, list[UnitRecord]]) -> list[str]:
    return [coin for coin in KNOWN_COINS if coin not in grouped]


def _hyphenated_active(records: Iterable[UnitRecord]) -> list[UnitRecord]:
    return [
        record
        for record in records
        if record.active_state == "active" and record.naming_variant == "hyphen"
    ]


def build_report(records: list[UnitRecord], listeners: list[ListenerRecord]) -> dict:
    active_agents = _group_active_by_coin(records, "agent")
    active_exporters = _group_active_by_coin(records, "exporter")
    duplicate_agents = _duplicates(active_agents)
    duplicate_exporters = _duplicates(active_exporters)
    hyphenated = _hyphenated_active(records)

    return {
        "policy": {
            "single_active_agent_per_coin": True,
            "single_active_exporter_per_coin": True,
            "expected_coins": list(KNOWN_COINS),
        },
        "active_agents_by_coin": {
            coin: [asdict(record) for record in items] for coin, items in sorted(active_agents.items())
        },
        "active_exporters_by_coin": {
            coin: [asdict(record) for record in items] for coin, items in sorted(active_exporters.items())
        },
        "duplicate_agents": {
            coin: [asdict(record) for record in items] for coin, items in sorted(duplicate_agents.items())
        },
        "duplicate_exporters": {
            coin: [asdict(record) for record in items] for coin, items in sorted(duplicate_exporters.items())
        },
        "missing_expected_agents": _missing_expected(active_agents),
        "missing_expected_exporters": _missing_expected(active_exporters),
        "active_hyphenated_units": [asdict(record) for record in hyphenated],
        "listeners": [asdict(listener) for listener in sorted(listeners, key=lambda item: item.port)],
        "all_units": [asdict(record) for record in records],
    }


def _render_summary(report: dict) -> str:
    lines: list[str] = []
    lines.append("Trading topology audit")
    lines.append("")

    dup_agents = report["duplicate_agents"]
    dup_exporters = report["duplicate_exporters"]
    missing_agents = report["missing_expected_agents"]
    missing_exporters = report["missing_expected_exporters"]
    hyphenated = report["active_hyphenated_units"]

    if dup_agents:
        lines.append("Duplicate active agents per coin:")
        for coin, items in dup_agents.items():
            names = ", ".join(item["unit_name"] for item in items)
            lines.append(f"- {coin}: {names}")
    else:
        lines.append("Duplicate active agents per coin: none")

    if dup_exporters:
        lines.append("")
        lines.append("Duplicate active exporters per coin:")
        for coin, items in dup_exporters.items():
            names = ", ".join(item["unit_name"] for item in items)
            lines.append(f"- {coin}: {names}")
    else:
        lines.append("Duplicate active exporters per coin: none")

    if missing_agents:
        lines.append("")
        lines.append("Missing expected agent coins:")
        for coin in missing_agents:
            lines.append(f"- {coin}")

    if missing_exporters:
        lines.append("")
        lines.append("Missing expected exporter coins:")
        for coin in missing_exporters:
            lines.append(f"- {coin}")

    if hyphenated:
        lines.append("")
        lines.append("Active hyphenated units:")
        for item in hyphenated:
            lines.append(f"- {item['unit_name']}")

    lines.append("")
    lines.append("Known listeners:")
    for listener in report["listeners"]:
        lines.append(f"- {listener['port']}: {listener['process']}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit remote trading topology for duplicate instances.")
    parser.add_argument("--host", default="192.168.15.2")
    parser.add_argument("--user", default="homelab")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    args = parser.parse_args()

    units_cmd = (
        "systemctl list-units --type=service --all --plain --no-legend --full "
        + " ".join(f"'{pattern}'" for pattern in UNIT_PATTERNS)
        + " || true"
    )
    listeners_cmd = f"ss -lntpH | grep -E '{PORT_PATTERN}' || true"

    try:
        units_raw = _run_ssh(args.user, args.host, units_cmd)
        listeners_raw = _run_ssh(args.user, args.host, listeners_cmd)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    report = build_report(parse_systemctl_units(units_raw), parse_listeners(listeners_raw))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(_render_summary(report))
        print("")
        print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
