#!/usr/bin/env python3
"""Generate a process tree view from CMDB load artifacts.

This produces a host-centric tree that groups:
- infrastructure services from netbox-load-package.json
- operational applications from glpi-load-package.json

The output is intended to be a process/service dependency map derived from the
CMDB, not a live Linux PID tree.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "deploy" / "cmdb" / "bootstrap" / "generated"
DEFAULT_JSON_OUTPUT = DEFAULT_INPUT_DIR / "cmdb-process-tree.json"
DEFAULT_MD_OUTPUT = DEFAULT_INPUT_DIR / "cmdb-process-tree.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_grouped_items(
    host_tree: dict[str, Any],
    items: list[dict[str, Any]],
    target_field: str,
    section_name: str,
) -> None:
    for item in items:
        target = str(item.get(target_field) or "unassigned").strip() or "unassigned"
        domain = str(item.get("domain") or "unknown").strip() or "unknown"
        kind = str(item.get("kind") or "unknown").strip() or "unknown"
        host_tree.setdefault(target, {})
        host_tree[target].setdefault(section_name, {})
        host_tree[target][section_name].setdefault(domain, {})
        host_tree[target][section_name][domain].setdefault(kind, [])
        host_tree[target][section_name][domain][kind].append(
            {
                "name": item["name"],
                "source": item.get("source", ""),
                "owner": item.get("recommended_owner", ""),
                "status": item.get("status", ""),
                "description": item.get("description", ""),
            }
        )


def build_tree(netbox_package: dict[str, Any], glpi_package: dict[str, Any]) -> dict[str, Any]:
    hosts_meta: dict[str, dict[str, Any]] = {}
    for device in netbox_package.get("devices", []):
        hosts_meta[device["name"]] = {
            "name": device["name"],
            "primary_ip4": device.get("primary_ip4", ""),
            "site": device.get("site", ""),
            "role": device.get("role", ""),
            "platform": device.get("platform", ""),
        }

    grouped: dict[str, Any] = {}
    add_grouped_items(grouped, netbox_package.get("service_candidates", []), "target_device", "infrastructure_services")
    add_grouped_items(grouped, glpi_package.get("applications_review", []), "target_computer", "operational_applications")

    hosts: list[dict[str, Any]] = []
    for host_name in sorted(grouped):
        sections = grouped[host_name]
        host_record = dict(hosts_meta.get(host_name, {"name": host_name, "primary_ip4": "", "site": "", "role": "", "platform": ""}))
        host_record["sections"] = {}
        for section_name in sorted(sections):
            section_domains = sections[section_name]
            host_record["sections"][section_name] = {}
            for domain in sorted(section_domains):
                domain_kinds = section_domains[domain]
                host_record["sections"][section_name][domain] = {}
                for kind in sorted(domain_kinds):
                    host_record["sections"][section_name][domain][kind] = sorted(
                        domain_kinds[kind],
                        key=lambda item: item["name"],
                    )
        hosts.append(host_record)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "netbox": "netbox-load-package.json",
            "glpi": "glpi-load-package.json",
        },
        "site": netbox_package.get("site", {}).get("name", glpi_package.get("entity", "unknown")),
        "hosts": hosts,
    }


def append_node(lines: list[str], prefix: str, label: str, is_last: bool) -> str:
    branch = "`-- " if is_last else "|-- "
    lines.append(f"{prefix}{branch}{label}")
    return prefix + ("    " if is_last else "|   ")


def render_markdown(tree: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CMDB Process Tree")
    lines.append("")
    lines.append(f"- Generated at: `{tree['generated_at']}`")
    lines.append(f"- Site: `{tree['site']}`")
    lines.append(f"- Hosts: `{len(tree['hosts'])}`")
    lines.append("")
    lines.append("This is a CMDB-derived process tree for services and applications.")
    lines.append("It is not a live PID tree.")
    lines.append("")
    lines.append("```text")
    lines.append(tree["site"])

    for host_index, host in enumerate(tree["hosts"]):
        host_last = host_index == len(tree["hosts"]) - 1
        host_label = host["name"]
        if host.get("primary_ip4"):
            host_label += f" [{host['primary_ip4']}]"
        if host.get("role"):
            host_label += f" <{host['role']}>"
        host_prefix = append_node(lines, "", host_label, host_last)

        section_items = list(host.get("sections", {}).items())
        for section_index, (section_name, domains) in enumerate(section_items):
            section_last = section_index == len(section_items) - 1
            section_prefix = append_node(lines, host_prefix, section_name, section_last)
            domain_items = list(domains.items())
            for domain_index, (domain, kinds) in enumerate(domain_items):
                domain_last = domain_index == len(domain_items) - 1
                domain_prefix = append_node(lines, section_prefix, domain, domain_last)
                kind_items = list(kinds.items())
                for kind_index, (kind, services) in enumerate(kind_items):
                    kind_last = kind_index == len(kind_items) - 1
                    kind_prefix = append_node(lines, domain_prefix, f"{kind} ({len(services)})", kind_last)
                    for service_index, service in enumerate(services):
                        service_last = service_index == len(services) - 1
                        label = service["name"]
                        if service.get("owner"):
                            label += f" [owner:{service['owner']}]"
                        if service.get("status"):
                            label += f" [status:{service['status']}]"
                        append_node(lines, kind_prefix, label, service_last)

    lines.append("```")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a process tree from CMDB artifacts")
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing netbox-load-package.json and glpi-load-package.json",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_JSON_OUTPUT),
        help="Path for the generated JSON tree",
    )
    parser.add_argument(
        "--md-output",
        default=str(DEFAULT_MD_OUTPUT),
        help="Path for the generated Markdown tree",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    json_output = Path(args.json_output).resolve()
    md_output = Path(args.md_output).resolve()

    netbox_package = load_json(input_dir / "netbox-load-package.json")
    glpi_package = load_json(input_dir / "glpi-load-package.json")
    tree = build_tree(netbox_package, glpi_package)

    json_output.write_text(json.dumps(tree, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_output.write_text(render_markdown(tree), encoding="utf-8")

    print(json.dumps({"ok": True, "json_output": str(json_output), "md_output": str(md_output)}))


if __name__ == "__main__":
    main()
