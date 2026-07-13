#!/usr/bin/env python3
"""Generate CMDB bootstrap artifacts from repository inventory and deploy files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
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


@dataclass
class TradingProfileInstance:
    instance: str
    symbol: str
    profile: str
    coin: str
    config_file: str
    dry_run: bool
    live_mode: bool
    metrics_port: int | None
    api_port: int | None
    kucoin_account: str
    activate_script: str | None


TRADING_CONFIG_RE = re.compile(
    r"^config_([A-Z0-9]+)_USDT_(shadow|conservative|aggressive)\.json$"
)
ACTIVATE_PROFILE_RE = re.compile(
    r'"([A-Z0-9]+_USDT_(?:shadow|conservative|aggressive)):(\d+):(\d+)"'
)
ENV_METRICS_PORT_RE = re.compile(r"^METRICS_PORT=(\d+)\s*$", re.MULTILINE)
ENV_API_PORT_RE = re.compile(r"^BTC_ENGINE_API_PORT=(\d+)\s*$", re.MULTILINE)
PROMETHEUS_TARGET_RE = re.compile(
    r"job_name:\s*'crypto-exporter-([a-z0-9_]+)'\s*"
    r".*?targets:\s*\['[^']*:(\d+)'\]\s*"
    r".*?coin:\s*'([^']+)'\s*"
    r".*?profile:\s*'([^']+)'",
    re.DOTALL,
)
AUTO_TRADING_SERVICE_PREFIXES = ("crypto-agent@", "crypto-exporter@")


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


def _parse_env_ports(env_path: Path) -> tuple[int | None, int | None]:
    if not env_path.exists():
        return None, None
    text = env_path.read_text(encoding="utf-8")
    metrics_match = ENV_METRICS_PORT_RE.search(text)
    api_match = ENV_API_PORT_RE.search(text)
    metrics = int(metrics_match.group(1)) if metrics_match else None
    api_port = int(api_match.group(1)) if api_match else None
    return metrics, api_port


def _collect_activate_script_ports(repo_root: Path) -> dict[str, tuple[int, int]]:
    ports: dict[str, tuple[int, int]] = {}
    for script in sorted(repo_root.glob("scripts/activate_*_trading_profiles.sh")):
        text = script.read_text(encoding="utf-8")
        for match in ACTIVATE_PROFILE_RE.finditer(text):
            ports[match.group(1)] = (int(match.group(2)), int(match.group(3)))
    return ports


def _collect_prometheus_exporter_ports(repo_root: Path) -> dict[tuple[str, str], int]:
    prom_path = repo_root / "monitoring" / "prometheus.yml"
    if not prom_path.exists():
        return {}
    text = prom_path.read_text(encoding="utf-8")
    mapping: dict[tuple[str, str], int] = {}
    for match in PROMETHEUS_TARGET_RE.finditer(text):
        coin = match.group(3)
        profile = match.group(4)
        mapping[(coin, profile)] = int(match.group(2))
    return mapping


def _infer_kucoin_account(config: dict[str, Any]) -> str:
    for key in (
        "_doge_live_notes",
        "_sol_live_notes",
        "_eth_live_notes",
        "_btc_live_notes",
        "_doge_dry_run_notes",
    ):
        notes = config.get(key)
        if isinstance(notes, dict):
            conta = str(notes.get("conta", "")).strip()
            if conta:
                return conta
    if config.get("kucoin_subaccount_name"):
        return f"subconta ({config['kucoin_subaccount_name']})"
    return "master TRADE (kucoin/homelab)"


def discover_trading_profiles(repo_root: Path) -> list[TradingProfileInstance]:
    """Descobre instâncias crypto-agent@COIN_USDT_profile a partir dos configs do repo."""
    agent_dir = repo_root / "btc_trading_agent"
    if not agent_dir.exists():
        return []

    activate_ports = _collect_activate_script_ports(repo_root)
    prom_ports = _collect_prometheus_exporter_ports(repo_root)
    instances: list[TradingProfileInstance] = []

    for config_path in sorted(agent_dir.glob("config_*_USDT_*.json")):
        match = TRADING_CONFIG_RE.match(config_path.name)
        if not match:
            continue
        coin, profile = match.group(1), match.group(2)
        instance = f"{coin}_USDT_{profile}"
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        symbol = str(cfg.get("symbol", f"{coin}-USDT"))

        env_candidates = [
            agent_dir / f"{instance}.env.example",
            agent_dir / f"{instance}.env",
        ]
        metrics_port, api_port = None, None
        for env_path in env_candidates:
            metrics_port, api_port = _parse_env_ports(env_path)
            if metrics_port is not None:
                break
        if instance in activate_ports:
            metrics_port, api_port = activate_ports[instance]
        if metrics_port is None:
            metrics_port = prom_ports.get((symbol, profile))

        activate_script = None
        for script in sorted(repo_root.glob("scripts/activate_*_trading_profiles.sh")):
            if f"{coin}_USDT_" in script.read_text(encoding="utf-8"):
                activate_script = safe_relative(script, repo_root)
                break

        instances.append(
            TradingProfileInstance(
                instance=instance,
                symbol=symbol,
                profile=profile,
                coin=coin,
                config_file=safe_relative(config_path, repo_root),
                dry_run=bool(cfg.get("dry_run", True)),
                live_mode=bool(cfg.get("live_mode", False)),
                metrics_port=metrics_port,
                api_port=api_port,
                kucoin_account=_infer_kucoin_account(cfg),
                activate_script=activate_script,
            )
        )

    return sorted(instances, key=lambda item: (item.coin, item.profile))


def _trading_service_annotation(
    instance: TradingProfileInstance,
    role: str,
) -> dict[str, Any]:
    coin_slug = instance.coin.lower()
    prom_slug = f"{coin_slug}_usdt_{instance.profile}"
    mode = "live" if instance.live_mode and not instance.dry_run else "dry_run"
    return {
        "description": (
            f"Trading {role} {instance.symbol} perfil {instance.profile} ({mode}) "
            f"— {instance.kucoin_account}."
        ),
        "domain": "trading",
        "symbol": instance.symbol,
        "profile": instance.profile,
        "config_file": instance.config_file,
        "dry_run": instance.dry_run,
        "live_mode": instance.live_mode,
        "metrics_port": instance.metrics_port,
        "api_port": instance.api_port,
        "kucoin_account": instance.kucoin_account,
        "systemd_instance": instance.instance,
        "prometheus_job": f"crypto-exporter-{prom_slug}",
        "activate_script": instance.activate_script,
        "critical": True,
        "auto_generated": True,
        "source": "scripts/cmdb/generate_cmdb_baseline.py",
    }


def sync_trading_overrides(repo_root: Path, instances: list[TradingProfileInstance]) -> bool:
    """Mescla anotações auto-geradas de perfis trading em cmdb-agent-overrides.json."""
    override_path = repo_root / "deploy" / "cmdb" / "bootstrap" / "cmdb-agent-overrides.json"
    overrides = load_overrides(repo_root)
    annotations: dict[str, Any] = dict(overrides.get("service_annotations", {}))

    managed_keys = {
        key
        for key, meta in annotations.items()
        if isinstance(meta, dict) and meta.get("auto_generated") and key.startswith(AUTO_TRADING_SERVICE_PREFIXES)
    }
    expected_keys: set[str] = set()
    for inst in instances:
        for role in ("agent", "exporter"):
            unit = f"crypto-{role}@{inst.instance}.service"
            expected_keys.add(unit)
            annotations[unit] = _trading_service_annotation(inst, role)

    for stale in managed_keys - expected_keys:
        annotations.pop(stale, None)

    new_overrides = {**overrides, "service_annotations": annotations}
    serialized = json.dumps(new_overrides, indent=2, ensure_ascii=False) + "\n"
    if override_path.exists() and override_path.read_text(encoding="utf-8") == serialized:
        return False
    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(serialized, encoding="utf-8")
    return True


def _staged_trading_config_files(repo_root: Path) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    staged: list[str] = []
    for line in output.splitlines():
        name = Path(line).name
        if TRADING_CONFIG_RE.match(name):
            staged.append(line.strip())
    return staged


def validate_staged_trading_profiles(
    repo_root: Path,
    instances: list[TradingProfileInstance],
) -> list[str]:
    """Retorna configs staged que não estão refletidos no baseline trading."""
    known_configs = {inst.config_file for inst in instances}
    missing: list[str] = []
    for rel_path in _staged_trading_config_files(repo_root):
        if rel_path not in known_configs:
            missing.append(rel_path)
    return missing


def load_overrides(repo_root: Path) -> dict[str, Any]:
    override_path = repo_root / "deploy" / "cmdb" / "bootstrap" / "cmdb-agent-overrides.json"
    if override_path.exists():
        return json.loads(override_path.read_text(encoding="utf-8"))
    return {}


def build_baseline(repo_root: Path, inventory_path: Path, output_dir: Path, site_name: str) -> dict[str, Any]:
    hosts = discover_inventory_hosts(inventory_path, site_name, repo_root)
    services = collect_repo_services(repo_root)
    trading_instances = discover_trading_profiles(repo_root)
    sync_trading_overrides(repo_root, trading_instances)
    overrides = load_overrides(repo_root)
    annotations = overrides.get("service_annotations", {})
    domain_counts = Counter(service.domain for service in services)
    critical_services = [asdict(service) for service in services if service.critical]
    mvp_domains = {"monitoring", "network", "identity", "storage"}
    annotated_services = [
        {
            "name": name,
            "source": meta.get("source", "deploy/cmdb/bootstrap/cmdb-agent-overrides.json"),
            **meta,
        }
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
    for inst in trading_instances:
        for role in ("agent", "exporter"):
            unit = f"crypto-{role}@{inst.instance}.service"
            applications.append(
                {
                    "name": unit,
                    "domain": "trading",
                    "kind": "systemd-instance",
                    "source": inst.config_file,
                    "recommended_owner": "application",
                    "candidate_system": "NetBox service model",
                }
            )

    known_app_names = {app["name"] for app in applications}
    for name, meta in annotations.items():
        if name in known_app_names or not isinstance(meta, dict):
            continue
        applications.append(
            {
                "name": name,
                "domain": meta.get("domain", infer_domain(name)),
                "kind": meta.get("kind", "annotated"),
                "source": meta.get("source", "deploy/cmdb/bootstrap/cmdb-agent-overrides.json"),
                "recommended_owner": "application",
                "candidate_system": meta.get("candidate_system", "GLPI review"),
                "status": meta.get("status"),
                "status_reason": meta.get("status_reason"),
            }
        )

    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "inventory_file": safe_relative(inventory_path, repo_root),
        "output_dir": safe_relative(output_dir, repo_root),
        "site_name": site_name,
        "summary": {
            "hosts": len(hosts),
            "repo_services": len(services),
            "trading_instances": len(trading_instances),
            "critical_services": len(critical_services),
            "domains": dict(sorted(domain_counts.items())),
        },
        "trading_instances": [asdict(inst) for inst in trading_instances],
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
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
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
    trading = baseline.get("trading_instances", [])
    if trading:
        lines.extend(
            [
                "",
                f"## Trading profile instances (`{summary.get('trading_instances', len(trading))}`)",
                "",
            ]
        )
        for inst in trading:
            mode = "live" if inst.get("live_mode") and not inst.get("dry_run") else "dry_run"
            ports = ""
            if inst.get("metrics_port"):
                ports = f", metrics `:{inst['metrics_port']}`"
            lines.append(
                f"- `{inst['instance']}` → `{inst['symbol']}` / `{inst['profile']}` "
                f"({mode}{ports}) — `{inst.get('kucoin_account', '')}`"
            )
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
    parser.add_argument(
        "--check-staged",
        action="store_true",
        help="Falha se configs trading staged não estiverem no baseline (uso em pre-commit).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    inventory_path = args.inventory_file.resolve()
    output_dir = args.output_dir.resolve()
    baseline = build_baseline(repo_root, inventory_path, output_dir, args.site_name)
    write_outputs(output_dir, baseline)
    trading_instances = baseline.get("trading_instances", [])

    if args.check_staged:
        missing = validate_staged_trading_profiles(
            repo_root,
            [TradingProfileInstance(**item) for item in trading_instances],
        )
        if missing:
            print(
                "❌ CMDB: configs trading staged sem entrada no baseline:\n"
                + "\n".join(f"  - {path}" for path in missing),
                file=sys.stderr,
            )
            return 1

    print(f"Wrote CMDB baseline to {output_dir}")
    if trading_instances:
        print(f"  trading instances: {len(trading_instances)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
