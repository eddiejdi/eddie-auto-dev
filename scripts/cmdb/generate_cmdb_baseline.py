#!/usr/bin/env python3
"""Generate CMDB bootstrap artifacts from repository inventory and deploy files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised via fallback parser tests if needed
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = REPO_ROOT / "config" / "inventory_homelab.yml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "deploy" / "cmdb" / "bootstrap" / "generated"

DOMAIN_RULES = (
    ("monitoring", ("grafana", "prometheus", "alertmanager", "exporter", "metrics", "monitor")),
    ("identity", ("authentik", "ldap", "sso", "oauth", "vault")),
    ("network", ("vpn", "wireguard", "cloudflared", "pihole", "dns", "dhcp", "proxy", "tunnel")),
    ("storage", ("ltfs", "storj", "tape", "backup", "nextcloud", "disk")),
    ("trading", ("btc", "trading", "kucoin", "candle")),
)


@dataclass
class InventoryHost:
    name: str
    primary_ip4: str
    ansible_user: str
    site: str
    role: str
    platform: str
    source: str


@dataclass
class RepoService:
    name: str
    domain: str
    source: str
    kind: str
    critical: bool


def infer_domain(*values: str) -> str:
    haystack = " ".join(values).lower()
    for domain, tokens in DOMAIN_RULES:
        if any(token in haystack for token in tokens):
            return domain
    return "operations"


def infer_role(name: str) -> str:
    lowered = name.lower()
    if "vpn" in lowered or "wireguard" in lowered:
        return "vpn-gateway"
    if "pihole" in lowered or "dns" in lowered or "dhcp" in lowered:
        return "network-service"
    if "grafana" in lowered or "prometheus" in lowered:
        return "monitoring-node"
    if "auth" in lowered or "vault" in lowered:
        return "identity-node"
    if "storj" in lowered or "ltfs" in lowered or "backup" in lowered:
        return "storage-node"
    return "compute-node"


def infer_platform(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".ps1") or "windows" in lowered or "win11" in lowered:
        return "windows"
    return "linux"


def load_yaml(path: Path) -> Any | None:
    if yaml is None:
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def extract_hosts_from_yaml(payload: Any, source: str, site_name: str) -> list[InventoryHost]:
    hosts: list[InventoryHost] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        raw_hosts = node.get("hosts")
        if isinstance(raw_hosts, dict):
            for name, metadata in raw_hosts.items():
                if not isinstance(metadata, dict):
                    metadata = {}
                hosts.append(
                    InventoryHost(
                        name=name,
                        primary_ip4=str(metadata.get("ansible_host", "")),
                        ansible_user=str(metadata.get("ansible_user", "")),
                        site=site_name,
                        role=infer_role(name),
                        platform=infer_platform(name),
                        source=source,
                    )
                )
        for value in node.values():
            walk(value)

    walk(payload)
    unique_hosts: dict[str, InventoryHost] = {host.name: host for host in hosts}
    return sorted(unique_hosts.values(), key=lambda host: host.name)


def extract_hosts_from_text(text: str, source: str, site_name: str) -> list[InventoryHost]:
    hosts: list[InventoryHost] = []
    in_hosts_block = False
    hosts_indent = 0
    pending_name: str | None = None
    pending_ip = ""
    pending_user = ""

    def flush_pending() -> None:
        nonlocal pending_name, pending_ip, pending_user
        if pending_name is None:
            return
        hosts.append(
            InventoryHost(
                name=pending_name,
                primary_ip4=pending_ip,
                ansible_user=pending_user,
                site=site_name,
                role=infer_role(pending_name),
                platform=infer_platform(pending_name),
                source=source,
            )
        )
        pending_name = None
        pending_ip = ""
        pending_user = ""

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line == "hosts:":
            flush_pending()
            in_hosts_block = True
            hosts_indent = indent
            continue
        if in_hosts_block and indent <= hosts_indent:
            flush_pending()
            in_hosts_block = False
        if not in_hosts_block:
            continue
        host_match = re.match(r"^([A-Za-z0-9._-]+):$", line)
        if host_match and indent > hosts_indent:
            flush_pending()
            pending_name = host_match.group(1)
            continue
        if pending_name is None:
            continue
        ip_match = re.match(r"^ansible_host:\s*(.+)$", line)
        if ip_match:
            pending_ip = ip_match.group(1).strip().strip("'\"")
            continue
        user_match = re.match(r"^ansible_user:\s*(.+)$", line)
        if user_match:
            pending_user = user_match.group(1).strip().strip("'\"")

    flush_pending()
    unique_hosts: dict[str, InventoryHost] = {host.name: host for host in hosts}
    return sorted(unique_hosts.values(), key=lambda host: host.name)


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def discover_inventory_hosts(path: Path, site_name: str, repo_root: Path) -> list[InventoryHost]:
    source = safe_relative(path, repo_root)
    payload = load_yaml(path)
    if payload is not None:
        return extract_hosts_from_yaml(payload, source, site_name)
    return extract_hosts_from_text(path.read_text(encoding="utf-8"), source, site_name)


def parse_compose_services(path: Path) -> list[str]:
    payload = load_yaml(path)
    if isinstance(payload, dict):
        services = payload.get("services")
        if isinstance(services, dict):
            return sorted(services.keys())
    services: list[str] = []
    in_services = False
    services_indent = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line == "services:":
            in_services = True
            services_indent = indent
            continue
        if in_services and indent <= services_indent:
            in_services = False
        if not in_services:
            continue
        match = re.match(r"^([A-Za-z0-9._-]+):$", line)
        if match and indent == services_indent + 2:
            services.append(match.group(1))
    return sorted(set(services))


def collect_repo_services(repo_root: Path) -> list[RepoService]:
    records: dict[tuple[str, str], RepoService] = {}

    def add_record(name: str, source: Path, kind: str) -> None:
        domain = infer_domain(name, str(source))
        key = (kind, name)
        critical = domain in {"monitoring", "identity", "network", "storage"}
        records[key] = RepoService(
            name=name,
            domain=domain,
            source=str(source.relative_to(repo_root)),
            kind=kind,
            critical=critical,
        )

    for pattern in ("systemd/*.service", "systemd/*.timer", "tools/**/*.service", "deploy/**/*.service"):
        for path in sorted(repo_root.glob(pattern)):
            add_record(path.name, path, "systemd")

    for pattern in ("docker/*.yml", "deploy/**/docker-compose*.yml", "forks/**/docker-compose*.yml", "tools/**/docker-compose*.yml"):
        for path in sorted(repo_root.glob(pattern)):
            for service_name in parse_compose_services(path):
                add_record(service_name, path, "compose")

    return sorted(records.values(), key=lambda record: (record.domain, record.kind, record.name))


def load_overrides(repo_root: Path) -> dict[str, Any]:
    override_path = repo_root / "deploy" / "cmdb" / "bootstrap" / "cmdb-agent-overrides.json"
    if override_path.exists():
        return json.loads(override_path.read_text(encoding="utf-8"))
    return {}


def build_baseline(repo_root: Path, inventory_path: Path, output_dir: Path, site_name: str) -> dict[str, Any]:
    hosts = discover_inventory_hosts(inventory_path, site_name, repo_root)
    services = collect_repo_services(repo_root)
    overrides = load_overrides(repo_root)
    annotations = overrides.get("service_annotations", {})
    domain_counts = Counter(service.domain for service in services)
    critical_services = [asdict(service) for service in services if service.critical]
    mvp_domains = {"monitoring", "network", "identity", "storage"}
    annotated_services = [
        {"name": name, **meta}
        for name, meta in annotations.items()
    ]
    applications = [
        {
            "name": service.name,
            "domain": service.domain,
            "kind": service.kind,
            "source": service.source,
            "recommended_owner": "platform" if service.domain in mvp_domains else "application",
            "candidate_system": "NetBox service model" if service.domain in mvp_domains else "GLPI review",
        }
        for service in services
    ]

    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "inventory_file": safe_relative(inventory_path, repo_root),
        "output_dir": safe_relative(output_dir, repo_root),
        "site_name": site_name,
        "summary": {
            "hosts": len(hosts),
            "repo_services": len(services),
            "critical_services": len(critical_services),
            "domains": dict(sorted(domain_counts.items())),
        },
        "netbox_devices": [asdict(host) for host in hosts],
        "glpi_computers": [
            {
                "name": host.name,
                "asset_type": "Computer",
                "location": host.site,
                "owner": host.ansible_user or "platform",
                "source": host.source,
            }
            for host in hosts
        ],
        "applications_review": applications,
        "mvp_focus": {
            "domains": sorted(mvp_domains),
            "critical_services": critical_services,
        },
        "annotated_services": annotated_services,
        "project": overrides.get("project", {}),
    }
    return baseline


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown_summary(baseline: dict[str, Any]) -> str:
    summary = baseline["summary"]
    project = baseline.get("project", {})
    lines = [
        "# CMDB Baseline",
        "",
        f"- Generated at: `{baseline['generated_at']}`",
        f"- Site: `{baseline['site_name']}`",
        f"- Hosts discovered: `{summary['hosts']}`",
        f"- Repo services discovered: `{summary['repo_services']}`",
        f"- Critical services flagged for MVP: `{summary['critical_services']}`",
    ]
    if project:
        lines += [
            f"- Project: [{project.get('name', '')}]({project.get('repository', '')})",
            f"- Owner: `{project.get('owner', '')}`",
        ]
    lines += [
        "",
        "## Domain counts",
        "",
    ]
    for domain, count in summary["domains"].items():
        lines.append(f"- `{domain}`: {count}")
    lines.extend(
        [
            "",
            "## NetBox seed candidates",
            "",
        ]
    )
    for device in baseline["netbox_devices"]:
        lines.append(
            f"- `{device['name']}` -> role `{device['role']}`, platform `{device['platform']}`, ip `{device['primary_ip4'] or 'review-needed'}`"
        )
    lines.extend(
        [
            "",
            "## MVP critical services",
            "",
        ]
    )
    for service in baseline["mvp_focus"]["critical_services"][:40]:
        lines.append(
            f"- `{service['name']}` ({service['domain']}, {service['kind']}) from `{service['source']}`"
        )
    annotated = baseline.get("annotated_services", [])
    if annotated:
        lines.extend(["", "## Serviços anotados manualmente", ""])
        for svc in annotated:
            name = svc.get("name", "?")
            desc = svc.get("description", "")
            depends = ", ".join(svc.get("depends_on", []))
            lines.append(f"### `{name}`")
            if desc:
                lines.append(f"- Descrição: {desc}")
            if depends:
                lines.append(f"- Depende de: `{depends}`")
            for k, v in svc.items():
                if k not in {"name", "description", "depends_on", "critical"}:
                    lines.append(f"- {k}: `{v}`")
            lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, baseline: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cmdb-baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "cmdb-baseline.md").write_text(
        render_markdown_summary(baseline),
        encoding="utf-8",
    )
    write_csv(output_dir / "netbox-devices.csv", baseline["netbox_devices"])
    write_csv(output_dir / "glpi-computers.csv", baseline["glpi_computers"])
    write_csv(output_dir / "applications-review.csv", baseline["applications_review"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--inventory-file", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-name", default="homelab-main")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    inventory_path = args.inventory_file.resolve()
    output_dir = args.output_dir.resolve()
    baseline = build_baseline(repo_root, inventory_path, output_dir, args.site_name)
    write_outputs(output_dir, baseline)
    print(f"Wrote CMDB baseline to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
