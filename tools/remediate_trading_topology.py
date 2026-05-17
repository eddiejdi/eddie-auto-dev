#!/usr/bin/env python3
"""Plan or apply trading topology remediation on the homelab host.

Default mode is dry-run. It enforces the policy:
- one active agent per coin;
- one active exporter per coin.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.audit_trading_topology import UnitRecord, build_report, parse_listeners, parse_systemctl_units

KNOWN_PROFILES = ("conservative", "aggressive", "default")
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
class RemediationDecision:
    coin: str
    role: str
    keep_unit: str
    disable_units: tuple[str, ...]
    rationale: str


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


def _fetch_units(user: str, host: str) -> list[UnitRecord]:
    units_cmd = (
        "systemctl list-units --type=service --all --plain --no-legend --full "
        + " ".join(f"'{pattern}'" for pattern in UNIT_PATTERNS)
        + " || true"
    )
    listeners_cmd = f"ss -lntpH | grep -E '{PORT_PATTERN}' || true"
    units_raw = _run_ssh(user, host, units_cmd)
    listeners_raw = _run_ssh(user, host, listeners_cmd)
    # Reuse listener parsing indirectly to keep same remote probes in the report output.
    _ = parse_listeners(listeners_raw)
    return parse_systemctl_units(units_raw)


def _score_unit(
    unit: UnitRecord,
    *,
    preferred_profile: str,
    prefer_legacy_exporter: bool,
) -> tuple[int, int, int, str]:
    profile_score = 0
    if unit.profile == preferred_profile:
        profile_score = 3
    elif unit.profile == "default":
        profile_score = 2
    elif unit.profile in KNOWN_PROFILES:
        profile_score = 1

    legacy_score = 0
    if unit.role == "exporter":
        legacy_score = 2 if (prefer_legacy_exporter and unit.is_legacy) else 1 if (not prefer_legacy_exporter and not unit.is_legacy) else 0
    else:
        legacy_score = 1 if not unit.is_legacy else 0

    naming_score = 1 if unit.naming_variant == "underscore" else 0
    return (profile_score, legacy_score, naming_score, unit.unit_name)


def choose_single_units(
    units: Iterable[UnitRecord],
    *,
    preferred_profile: str,
    prefer_legacy_exporter: bool,
) -> list[RemediationDecision]:
    grouped: dict[tuple[str, str], list[UnitRecord]] = defaultdict(list)
    for unit in units:
        if unit.active_state != "active" or not unit.coin:
            continue
        grouped[(unit.coin, unit.role)].append(unit)

    decisions: list[RemediationDecision] = []
    for (coin, role), items in sorted(grouped.items()):
        if len(items) <= 1:
            continue
        ordered = sorted(
            items,
            key=lambda item: _score_unit(
                item,
                preferred_profile=preferred_profile,
                prefer_legacy_exporter=prefer_legacy_exporter,
            ),
            reverse=True,
        )
        keep = ordered[0]
        disable = tuple(item.unit_name for item in ordered[1:])
        rationale = (
            f"keep={keep.unit_name} by profile preference={preferred_profile}, "
            f"prefer_legacy_exporter={prefer_legacy_exporter}"
        )
        decisions.append(
            RemediationDecision(
                coin=coin,
                role=role,
                keep_unit=keep.unit_name,
                disable_units=disable,
                rationale=rationale,
            )
        )
    return decisions


def build_remediation_commands(decisions: Iterable[RemediationDecision]) -> list[str]:
    commands: list[str] = []
    for decision in decisions:
        if not decision.disable_units:
            continue
        units = " ".join(decision.disable_units)
        commands.append(f"sudo systemctl stop {units}")
        commands.append(f"sudo systemctl disable {units}")
    if commands:
        commands.append("sudo systemctl daemon-reload")
    return commands


def apply_commands(user: str, host: str, commands: Iterable[str]) -> list[dict[str, str | int]]:
    results: list[dict[str, str | int]] = []
    for command in commands:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", f"{user}@{host}", command],
            check=False,
            capture_output=True,
            text=True,
        )
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or apply single-instance-per-coin remediation.")
    parser.add_argument("--host", default="192.168.15.2")
    parser.add_argument("--user", default="homelab")
    parser.add_argument("--preferred-profile", choices=KNOWN_PROFILES, default="conservative")
    parser.add_argument(
        "--prefer-legacy-exporter",
        action="store_true",
        help="Prefer legacy exporter units such as autocoinbot-exporter.service when deduplicating exporters.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute stop/disable commands on the remote host. Default is dry-run.",
    )
    args = parser.parse_args()

    try:
        units = _fetch_units(args.user, args.host)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    report = build_report(units, [])
    decisions = choose_single_units(
        units,
        preferred_profile=args.preferred_profile,
        prefer_legacy_exporter=args.prefer_legacy_exporter,
    )
    commands = build_remediation_commands(decisions)

    payload: dict[str, object] = {
        "mode": "apply" if args.apply else "dry-run",
        "policy": {
            "single_active_agent_per_coin": True,
            "single_active_exporter_per_coin": True,
            "preferred_profile": args.preferred_profile,
            "prefer_legacy_exporter": args.prefer_legacy_exporter,
        },
        "decisions": [
            {
                "coin": decision.coin,
                "role": decision.role,
                "keep_unit": decision.keep_unit,
                "disable_units": list(decision.disable_units),
                "rationale": decision.rationale,
            }
            for decision in decisions
        ],
        "commands": commands,
        "duplicates": {
            "agents": report["duplicate_agents"],
            "exporters": report["duplicate_exporters"],
        },
    }

    if args.apply and commands:
        payload["apply_results"] = apply_commands(args.user, args.host, commands)

    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
