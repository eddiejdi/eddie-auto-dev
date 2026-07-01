#!/usr/bin/env python3
"""CMDB agent for discovery, review, and load-package generation.

This agent reuses the repository CMDB baseline builder and adds:
- review findings for fields that still need operator confirmation
- NetBox-oriented load packages
- GLPI-oriented load packages
- human-readable reports for the import workflow

All apply actions remain dry-run by default. Live execution is supported for
the current NetBox and GLPI mappings and is designed to be idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from ipaddress import ip_address, ip_interface
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from scripts.cmdb.generate_cmdb_baseline import (
    DEFAULT_INVENTORY,
    DEFAULT_OUTPUT_DIR,
    REPO_ROOT,
    build_baseline,
    write_csv,
    write_outputs,
)

router = APIRouter()


BASELINE_FILE_NAMES = (
    "cmdb-baseline.json",
    "cmdb-baseline.md",
    "netbox-devices.csv",
    "glpi-computers.csv",
    "applications-review.csv",
)

AGENT_FILE_NAMES = (
    "cmdb-agent-report.json",
    "cmdb-agent-report.md",
    "netbox-load-package.json",
    "netbox-apply-plan.json",
    "glpi-load-package.json",
    "glpi-apply-plan.json",
    "glpi-apply.sql",
    "review-queue.json",
    "netbox-device-import.csv",
    "glpi-computer-import.csv",
    "netbox-service-candidates.csv",
    "glpi-application-review.csv",
)

DOMAIN_COLORS = {
    "identity": "1565c0",
    "monitoring": "2e7d32",
    "network": "ef6c00",
    "storage": "6a1b9a",
    "trading": "00897b",
    "operations": "546e7a",
}

DISCOVERED_SOFTWARE_VERSION = "cmdb-discovered"
DEFAULT_OVERRIDES_RELATIVE_PATH = Path("deploy/cmdb/bootstrap/cmdb-agent-overrides.json")
GLPI_SOFTWARE_CATEGORY_ROOT = "CMDB Imported"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "item"


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def ensure_host_cidr(raw_ip: str) -> tuple[str | None, str | None, bool]:
    value = str(raw_ip or "").strip()
    if not value:
        return None, None, False
    if "/" in value:
        iface = ip_interface(value)
        return str(iface), str(iface.network), False
    iface = ip_interface(f"{value}/32")
    return str(iface), None, True


def infer_device_type(platform: str) -> str:
    lowered = platform.lower()
    if "windows" in lowered:
        return "Generic Windows Host"
    return "Generic Linux Host"


def infer_manufacturer(platform: str) -> str:
    lowered = platform.lower()
    if "windows" in lowered:
        return "Microsoft"
    return "RPA4All"


def location_slug(site_name: str) -> str:
    return slugify(site_name)


def choose_primary_target_name(names: list[str], preferred_name: str = "homelab") -> tuple[str | None, str]:
    candidates = sorted({str(name).strip() for name in names if str(name).strip()})
    if not candidates:
        return None, "unassigned"
    if len(candidates) == 1:
        return candidates[0], "single-target"
    if preferred_name in candidates:
        return preferred_name, "preferred-target"
    return candidates[0], "first-target"


def inventory_role_name(domain: str) -> str:
    normalized = str(domain or "operations").strip() or "operations"
    return f"{normalized}-service"


def domain_display_name(domain: str) -> str:
    normalized = str(domain or "operations").strip() or "operations"
    return " ".join(part.capitalize() for part in normalized.replace("_", "-").split("-"))


def load_optional_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_target_name(
    item_name: str,
    available_names: list[str],
    preferred_name: str,
    service_overrides: dict[str, Any],
    default_target_name: str | None,
    field_name: str,
) -> tuple[str | None, str]:
    available = sorted({str(name).strip() for name in available_names if str(name).strip()})
    override_target = str(service_overrides.get(item_name, {}).get(field_name) or "").strip()
    if override_target:
        if override_target in available:
            return override_target, "override-service"
        return None, "override-service-missing-target"

    default_target = str(default_target_name or "").strip()
    if default_target:
        if default_target in available:
            return default_target, "override-default"
        return None, "override-default-missing-target"

    return choose_primary_target_name(available, preferred_name=preferred_name)


@dataclass
class ReviewFinding:
    severity: Literal["info", "warning", "error"]
    code: str
    target_system: Literal["netbox", "glpi", "shared"]
    subject: str
    message: str
    recommendation: str


class CmdbAgentRunRequest(BaseModel):
    repo_root: str | None = Field(default=None, description="Repository root to scan")
    inventory_file: str | None = Field(default=None, description="Inventory file path")
    output_dir: str | None = Field(default=None, description="Directory where artifacts are written")
    overrides_file: str | None = Field(default=None, description="Optional JSON overrides file for CMDB enrichment")
    site_name: str = Field(default="homelab-main", min_length=2, max_length=120)
    write_outputs: bool = Field(default=True)


class CmdbNetboxApplyRequest(BaseModel):
    package_path: str = Field(
        default=str(DEFAULT_OUTPUT_DIR / "netbox-load-package.json"),
        description="Path to netbox-load-package.json",
    )
    container_name: str = Field(default="cmdb-netbox", min_length=3, max_length=120)
    dry_run: bool = Field(default=True)


class CmdbGlpiApplyRequest(BaseModel):
    package_path: str = Field(
        default=str(DEFAULT_OUTPUT_DIR / "glpi-load-package.json"),
        description="Path to glpi-load-package.json",
    )
    env_file: str = Field(
        default=str(REPO_ROOT / "deploy/cmdb/.env"),
        description="Path to the GLPI stack .env file on the execution host",
    )
    db_container: str | None = Field(default=None, description="Optional explicit GLPI DB container name")
    execute: bool = Field(default=False)


class CmdbLoadAgent:
    """Prepare NetBox and GLPI load packages from repository CMDB sources."""

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        inventory_file: Path = DEFAULT_INVENTORY,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        overrides_file: Path | None = None,
        site_name: str = "homelab-main",
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.inventory_file = inventory_file.resolve()
        self.output_dir = output_dir.resolve()
        self.overrides_file = (
            overrides_file.resolve() if overrides_file is not None else (self.repo_root / DEFAULT_OVERRIDES_RELATIVE_PATH)
        )
        self.site_name = site_name

    def run(self, write_artifacts: bool = True) -> dict[str, Any]:
        if not self.repo_root.exists():
            raise FileNotFoundError(f"Repository root not found: {self.repo_root}")
        if not self.inventory_file.exists():
            raise FileNotFoundError(f"Inventory file not found: {self.inventory_file}")

        baseline = build_baseline(
            repo_root=self.repo_root,
            inventory_path=self.inventory_file,
            output_dir=self.output_dir,
            site_name=self.site_name,
        )
        overrides = load_optional_json_file(self.overrides_file)
        baseline = self._apply_overrides(baseline, overrides)
        findings = self._review_baseline(baseline)
        netbox_package = self._build_netbox_load_package(baseline, findings, overrides)
        glpi_package = self._build_glpi_load_package(baseline, overrides)
        findings.extend(self._review_packages(netbox_package, glpi_package))
        netbox_apply_plan = build_netbox_apply_plan(netbox_package)
        glpi_apply_plan = build_glpi_apply_plan(glpi_package)
        review_queue = self._build_review_queue(baseline, findings)
        report = self._build_report(
            baseline=baseline,
            findings=findings,
            netbox_package=netbox_package,
            glpi_package=glpi_package,
            netbox_apply_plan=netbox_apply_plan,
            glpi_apply_plan=glpi_apply_plan,
            review_queue=review_queue,
        )

        if write_artifacts:
            self._write_artifacts(
                baseline=baseline,
                report=report,
                netbox_package=netbox_package,
                glpi_package=glpi_package,
                netbox_apply_plan=netbox_apply_plan,
                glpi_apply_plan=glpi_apply_plan,
                review_queue=review_queue,
            )
            report["artifacts"] = self._artifact_map()
        else:
            report["artifacts"] = {}

        return report

    def _apply_overrides(self, baseline: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        host_overrides = overrides.get("hosts") or {}
        if not host_overrides:
            return baseline

        for section_name in ("netbox_devices", "glpi_computers"):
            updated_rows: list[dict[str, Any]] = []
            for row in baseline.get(section_name, []):
                if not isinstance(row, dict):
                    updated_rows.append(row)
                    continue
                override = host_overrides.get(row.get("name")) or {}
                merged = dict(row)
                for key in ("primary_ip4", "ansible_user", "owner", "site", "role", "platform"):
                    value = override.get(key)
                    if value not in (None, ""):
                        merged[key] = value
                updated_rows.append(merged)
            baseline[section_name] = updated_rows
        return baseline

    def _review_baseline(self, baseline: dict[str, Any]) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []

        for device in baseline["netbox_devices"]:
            name = device["name"]
            raw_ip = str(device.get("primary_ip4") or "").strip()
            ansible_user = str(device.get("ansible_user") or "").strip()
            role = str(device.get("role") or "").strip()
            platform = str(device.get("platform") or "").strip()

            if not raw_ip:
                findings.append(
                    ReviewFinding(
                        severity="warning",
                        code="missing-primary-ip4",
                        target_system="netbox",
                        subject=name,
                        message=f"Host `{name}` has no primary IPv4 address in inventory.",
                        recommendation="Confirm the management IP before importing the device into NetBox.",
                    )
                )
            elif "/" not in raw_ip:
                findings.append(
                    ReviewFinding(
                        severity="info",
                        code="missing-prefix-length",
                        target_system="netbox",
                        subject=name,
                        message=f"Host `{name}` has IPv4 `{raw_ip}` without prefix length.",
                        recommendation="Review the network mask; the load package will use /32 until the real prefix is confirmed.",
                    )
                )

            if not ansible_user:
                findings.append(
                    ReviewFinding(
                        severity="warning",
                        code="missing-owner",
                        target_system="glpi",
                        subject=name,
                        message=f"Host `{name}` has no ansible_user/owner assigned.",
                        recommendation="Assign the operational owner before the GLPI import review is closed.",
                    )
                )

            if not role:
                findings.append(
                    ReviewFinding(
                        severity="warning",
                        code="missing-role",
                        target_system="netbox",
                        subject=name,
                        message=f"Host `{name}` has no inferred role.",
                        recommendation="Set the intended device role for NetBox classification.",
                    )
                )

            if not platform:
                findings.append(
                    ReviewFinding(
                        severity="warning",
                        code="missing-platform",
                        target_system="shared",
                        subject=name,
                        message=f"Host `{name}` has no inferred platform.",
                        recommendation="Review whether the asset should be loaded as Linux, Windows, or another platform.",
                    )
                )

        return findings

    def _review_packages(
        self,
        netbox_package: dict[str, Any],
        glpi_package: dict[str, Any],
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []

        for item in netbox_package["service_candidates"]:
            if not item.get("review_required"):
                continue
            findings.append(
                ReviewFinding(
                    severity="warning" if not item.get("target_device") else "info",
                    code="service-target-review",
                    target_system="netbox",
                    subject=item["name"],
                    message=(
                        f"Service `{item['name']}` requires NetBox target review"
                        f" from `{item['source']}` with assignment `{item.get('target_assignment')}`."
                    ),
                    recommendation=(
                        "Set an explicit target device in deploy/cmdb/bootstrap/cmdb-agent-overrides.json"
                        " before the next import wave."
                    ),
                )
            )

        for item in glpi_package["applications_review"]:
            if not item.get("review_required"):
                continue
            findings.append(
                ReviewFinding(
                    severity="warning" if not item.get("target_computer") else "info",
                    code="application-target-review",
                    target_system="glpi",
                    subject=item["name"],
                    message=(
                        f"Application `{item['name']}` requires GLPI target review"
                        f" from `{item['source']}` with assignment `{item.get('target_assignment')}`."
                    ),
                    recommendation=(
                        "Set an explicit target computer in deploy/cmdb/bootstrap/cmdb-agent-overrides.json"
                        " before the next import wave."
                    ),
                )
            )

        return findings

    def _build_netbox_load_package(
        self,
        baseline: dict[str, Any],
        findings: list[ReviewFinding],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        roles: dict[str, dict[str, str]] = {}
        platforms: dict[str, dict[str, str]] = {}
        manufacturers: dict[str, dict[str, str]] = {}
        device_types: dict[str, dict[str, str]] = {}
        prefixes: dict[str, dict[str, str]] = {}
        devices: list[dict[str, Any]] = []
        ip_addresses: list[dict[str, Any]] = []
        interfaces: list[dict[str, Any]] = []

        for host in baseline["netbox_devices"]:
            role_name = host["role"] or "review-needed"
            platform_name = host["platform"] or "review-needed"
            manufacturer_name = infer_manufacturer(platform_name)
            device_type_name = infer_device_type(platform_name)
            primary_cidr, network_prefix, prefix_was_assumed = ensure_host_cidr(host.get("primary_ip4", ""))

            roles[role_name] = {"name": role_name, "slug": slugify(role_name), "color": "9e9e9e"}
            platforms[platform_name] = {"name": platform_name, "slug": slugify(platform_name)}
            manufacturers[manufacturer_name] = {"name": manufacturer_name, "slug": slugify(manufacturer_name)}

            device_type_key = f"{manufacturer_name}::{device_type_name}"
            device_types[device_type_key] = {
                "manufacturer": manufacturer_name,
                "model": device_type_name,
                "slug": slugify(device_type_name),
                "u_height": 1,
                "is_full_depth": False,
            }

            devices.append(
                {
                    "name": host["name"],
                    "site": host["site"],
                    "role": role_name,
                    "platform": platform_name,
                    "manufacturer": manufacturer_name,
                    "device_type": device_type_name,
                    "status": "active",
                    "management_interface": "mgmt0",
                    "primary_ip4": primary_cidr,
                    "primary_ip4_raw": host.get("primary_ip4") or "",
                    "source": host["source"],
                    "ansible_user": host["ansible_user"],
                    "review_required": prefix_was_assumed,
                    "primary_ip4_was_assumed": prefix_was_assumed,
                }
            )

            interfaces.append(
                {
                    "device": host["name"],
                    "name": "mgmt0",
                    "type": "virtual",
                }
            )

            if primary_cidr:
                ip_addresses.append(
                    {
                        "address": primary_cidr,
                        "status": "active",
                        "assigned_device": host["name"],
                        "assigned_interface": "mgmt0",
                        "source": host["source"],
                    }
                )
            if network_prefix:
                prefixes[network_prefix] = {
                    "prefix": network_prefix,
                    "site": host["site"],
                    "status": "active",
                    "source": host["source"],
                }

        available_device_names = [item["name"] for item in devices]
        default_target_device = (overrides.get("defaults") or {}).get("target_device")
        service_overrides = overrides.get("services") or {}
        services: list[dict[str, Any]] = []
        for item in baseline["applications_review"]:
            if item["candidate_system"] != "NetBox service model":
                continue
            target_device, target_assignment = resolve_target_name(
                item["name"],
                available_device_names,
                preferred_name="homelab",
                service_overrides=service_overrides,
                default_target_name=default_target_device,
                field_name="target_device",
            )
            services.append(
                {
                    "name": item["name"],
                    "domain": item["domain"],
                    "kind": item["kind"],
                    "source": item["source"],
                    "description": item.get("description", ""),
                    "recommended_owner": item["recommended_owner"],
                    "status": item.get("status", "active"),
                    "status_reason": item.get("status_reason", ""),
                    "target_device": target_device,
                    "target_assignment": target_assignment,
                    "review_required": target_assignment
                    not in {"single-target", "override-default", "override-service"},
                }
            )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "site": {
                "name": self.site_name,
                "slug": location_slug(self.site_name),
            },
            "manufacturers": sorted(manufacturers.values(), key=lambda item: item["name"]),
            "device_roles": sorted(roles.values(), key=lambda item: item["name"]),
            "platforms": sorted(platforms.values(), key=lambda item: item["name"]),
            "device_types": sorted(device_types.values(), key=lambda item: (item["manufacturer"], item["model"])),
            "devices": devices,
            "interfaces": interfaces,
            "ip_addresses": ip_addresses,
            "prefixes": sorted(prefixes.values(), key=lambda item: item["prefix"]),
            "service_candidates": services,
            "review_findings": [
                asdict(item) for item in findings if item.target_system in {"netbox", "shared"}
            ],
        }

    def _build_glpi_load_package(self, baseline: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        computers: list[dict[str, Any]] = []
        review_services: list[dict[str, Any]] = []

        for host in baseline["netbox_devices"]:
            computers.append(
                {
                    "name": host["name"],
                    "asset_type": "Computer",
                    "location": host["site"],
                    "owner": host["ansible_user"] or "platform",
                    "platform": host["platform"] or "review-needed",
                    "comment": f"Imported from {host['source']}",
                    "source": host["source"],
                }
            )

        available_computer_names = [item["name"] for item in computers]
        default_target_computer = (overrides.get("defaults") or {}).get("target_computer")
        service_overrides = overrides.get("services") or {}
        for item in baseline["applications_review"]:
            if item["candidate_system"] == "GLPI review":
                target_computer, target_assignment = resolve_target_name(
                    item["name"],
                    available_computer_names,
                    preferred_name="homelab",
                    service_overrides=service_overrides,
                    default_target_name=default_target_computer,
                    field_name="target_computer",
                )
                review_services.append(
                    {
                        **item,
                        "target_computer": target_computer,
                        "target_assignment": target_assignment,
                        "review_required": target_assignment not in {"single-target", "override-default", "override-service"},
                    }
                )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entity": self.site_name,
            "computers": computers,
            "applications_review": review_services,
            "owners": sorted({row["owner"] for row in computers}),
        }

    def _build_review_queue(
        self,
        baseline: dict[str, Any],
        findings: list[ReviewFinding],
    ) -> list[dict[str, Any]]:
        queue: list[dict[str, Any]] = []

        for finding in findings:
            queue.append(
                {
                    "queue": finding.target_system,
                    "severity": finding.severity,
                    "code": finding.code,
                    "subject": finding.subject,
                    "message": finding.message,
                    "recommendation": finding.recommendation,
                }
            )

        return queue

    def _build_report(
        self,
        baseline: dict[str, Any],
        findings: list[ReviewFinding],
        netbox_package: dict[str, Any],
        glpi_package: dict[str, Any],
        netbox_apply_plan: dict[str, Any],
        glpi_apply_plan: dict[str, Any],
        review_queue: list[dict[str, Any]],
    ) -> dict[str, Any]:
        severity_counts = dict(sorted(Counter(item.severity for item in findings).items()))
        target_counts = dict(sorted(Counter(item.target_system for item in findings).items()))
        next_steps = [
            "Review the remaining items in review-queue.json before closing the import wave.",
            "Keep deploy/cmdb/bootstrap/cmdb-agent-overrides.json aligned with the real host CIDRs and default CMDB targets.",
            "Dry-run or apply NetBox assets from netbox-load-package.json using the generated netbox-apply-plan.json.",
            "Dry-run or apply GLPI computers/software from glpi-load-package.json and glpi-apply-plan.json, then reconcile inferred ownership and target links.",
        ]

        return {
            "ok": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(self.repo_root),
            "inventory_file": str(self.inventory_file),
            "output_dir": str(self.output_dir),
            "site_name": self.site_name,
            "summary": {
                **baseline["summary"],
                "review_findings": len(findings),
                "review_queue_items": len(review_queue),
                "netbox_devices_ready": len(netbox_package["devices"]),
                "glpi_computers_ready": len(glpi_package["computers"]),
                "netbox_apply_supported": netbox_apply_plan["execution_supported"],
                "glpi_apply_supported": glpi_apply_plan["execution_supported"],
            },
            "review_summary": {
                "by_severity": severity_counts,
                "by_target_system": target_counts,
            },
            "findings": [asdict(item) for item in findings],
            "next_steps": next_steps,
        }

    def _write_artifacts(
        self,
        baseline: dict[str, Any],
        report: dict[str, Any],
        netbox_package: dict[str, Any],
        glpi_package: dict[str, Any],
        netbox_apply_plan: dict[str, Any],
        glpi_apply_plan: dict[str, Any],
        review_queue: list[dict[str, Any]],
    ) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        write_outputs(self.output_dir, baseline)
        self._write_json(self.output_dir / "cmdb-agent-report.json", report)
        self._write_json(self.output_dir / "netbox-load-package.json", netbox_package)
        self._write_json(self.output_dir / "netbox-apply-plan.json", netbox_apply_plan)
        self._write_json(self.output_dir / "glpi-load-package.json", glpi_package)
        self._write_json(self.output_dir / "glpi-apply-plan.json", glpi_apply_plan)
        (self.output_dir / "glpi-apply.sql").write_text(
            build_glpi_sql_script(glpi_package),
            encoding="utf-8",
        )
        self._write_json(self.output_dir / "review-queue.json", review_queue)
        (self.output_dir / "cmdb-agent-report.md").write_text(
            self._render_markdown_report(report),
            encoding="utf-8",
        )

        write_csv(
            self.output_dir / "netbox-device-import.csv",
            [
                {
                    "name": item["name"],
                    "site": item["site"],
                    "role": item["role"],
                    "platform": item["platform"],
                    "manufacturer": item["manufacturer"],
                    "device_type": item["device_type"],
                    "primary_ip4": item["primary_ip4"] or "",
                    "status": item["status"],
                    "source": item["source"],
                    "review_required": item["review_required"],
                }
                for item in netbox_package["devices"]
            ],
        )
        write_csv(self.output_dir / "glpi-computer-import.csv", glpi_package["computers"])
        write_csv(self.output_dir / "netbox-service-candidates.csv", netbox_package["service_candidates"])
        write_csv(self.output_dir / "glpi-application-review.csv", glpi_package["applications_review"])

    def _artifact_map(self) -> dict[str, str]:
        names = list(BASELINE_FILE_NAMES) + list(AGENT_FILE_NAMES)
        return {
            name: safe_relative(self.output_dir / name, self.repo_root)
            for name in names
            if (self.output_dir / name).exists()
        }

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def _render_markdown_report(self, report: dict[str, Any]) -> str:
        summary = report["summary"]
        review_summary = report["review_summary"]
        lines = [
            "# CMDB Agent Report",
            "",
            f"- Generated at: `{report['generated_at']}`",
            f"- Site: `{report['site_name']}`",
            f"- Hosts discovered: `{summary['hosts']}`",
            f"- Repo services discovered: `{summary['repo_services']}`",
            f"- NetBox devices ready: `{summary['netbox_devices_ready']}`",
            f"- GLPI computers ready: `{summary['glpi_computers_ready']}`",
            f"- Review findings: `{summary['review_findings']}`",
            f"- NetBox apply supported: `{summary['netbox_apply_supported']}`",
            f"- GLPI apply supported: `{summary['glpi_apply_supported']}`",
            "",
            "## Findings by severity",
            "",
        ]
        for severity, count in review_summary["by_severity"].items():
            lines.append(f"- `{severity}`: {count}")
        lines.extend(["", "## Findings by target system", ""])
        for target, count in review_summary["by_target_system"].items():
            lines.append(f"- `{target}`: {count}")
        lines.extend(["", "## Next steps", ""])
        for step in report["next_steps"]:
            lines.append(f"- {step}")
        return "\n".join(lines) + "\n"


def build_netbox_apply_plan(package: dict[str, Any], container_name: str = "cmdb-netbox") -> dict[str, Any]:
    review_required = [item["name"] for item in package["devices"] if item.get("review_required")]
    targeted_services = [item for item in package["service_candidates"] if item.get("target_device")]
    service_review_required = [item["name"] for item in package["service_candidates"] if item.get("review_required")]
    inventory_roles = {inventory_role_name(item.get("domain", "operations")) for item in targeted_services}
    return {
        "target_system": "netbox",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_supported": True,
        "default_strategy": "docker-manage-shell",
        "default_container_name": container_name,
        "counts": {
            "sites": 1,
            "manufacturers": len(package["manufacturers"]),
            "device_roles": len(package["device_roles"]),
            "platforms": len(package["platforms"]),
            "device_types": len(package["device_types"]),
            "devices": len(package["devices"]),
            "interfaces": len(package["interfaces"]),
            "ip_addresses": len(package["ip_addresses"]),
            "prefixes": len(package["prefixes"]),
            "inventory_item_roles": len(inventory_roles),
            "inventory_items": len(targeted_services),
            "service_candidates_review_required": len(service_review_required),
        },
        "review_required_devices": review_required,
        "review_required_services": service_review_required,
        "skipped_sections": [],
        "notes": [
            "The importer is idempotent for sites, roles, manufacturers, platforms, device types, devices, interfaces, IPs, prefixes, and inferred service inventory items.",
            "If a device IP came from inventory without prefix length, the importer preserves an existing wider prefix/IP assignment instead of downgrading it to /32.",
            "NetBox service candidates are materialized as InventoryItem records on the inferred target device because the baseline does not currently expose protocol/port data for the native NetBox service model.",
        ],
    }


def build_glpi_apply_plan(package: dict[str, Any]) -> dict[str, Any]:
    unresolved_owner_candidates = sorted({row["owner"] for row in package["computers"] if row.get("owner")})
    linked_applications = [item for item in package["applications_review"] if item.get("target_computer")]
    review_required_applications = [item["name"] for item in package["applications_review"] if item.get("review_required")]
    software_categories = sorted({item.get("domain") or "operations" for item in package["applications_review"]})
    return {
        "target_system": "glpi",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_supported": True,
        "default_strategy": "docker-mariadb-sql",
        "counts": {
            "computers": len(package["computers"]),
            "applications": len(package["applications_review"]),
            "software_links": len(linked_applications),
            "software_categories": len(software_categories),
            "owners": len(package["owners"]),
        },
        "owner_candidates": unresolved_owner_candidates,
        "review_required_applications": review_required_applications,
        "notes": [
            "The current GLPI writer upserts computers by name in entity 0 and preserves unresolved owners in the contact field.",
            "Applications are upserted as software catalog entries, categorized by domain, assigned a managed discovery version, and linked idempotently to the inferred target computer when one is available.",
        ],
    }


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Package file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sql_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "''")


def build_glpi_sql_script(package: dict[str, Any]) -> str:
    statements = [
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
    ]
    computer_names = [sql_escape(row["name"]) for row in package["computers"] if row.get("name")]
    category_root_name = sql_escape(GLPI_SOFTWARE_CATEGORY_ROOT)
    category_root_comment = sql_escape("Software categories managed by the CMDB agent")
    category_domains = sorted({str(row.get("domain") or "operations").strip() or "operations" for row in package["applications_review"]})

    for row in package["computers"]:
        name = sql_escape(row["name"])
        owner = sql_escape(row.get("owner") or "")
        platform = sql_escape(row.get("platform") or "")
        location = sql_escape(row.get("location") or "")
        source = sql_escape(row.get("source") or "")
        comment = sql_escape(
            f"{row.get('comment') or ''}\nLocation: {row.get('location') or ''}\n"
            f"Platform: {row.get('platform') or ''}\nSource: {row.get('source') or ''}"
        )
        statements.extend(
            [
                f"SET @owner_name = '{owner}';",
                "SET @owner_id = COALESCE((SELECT id FROM glpi_users WHERE name = @owner_name LIMIT 1), 0);",
                f"UPDATE glpi_computers SET "
                f"contact = '{owner}', "
                f"comment = '{comment}', "
                f"users_id = @owner_id, "
                f"users_id_tech = @owner_id, "
                "is_deleted = 0, "
                "is_dynamic = 0, "
                "is_recursive = 1, "
                "date_mod = NOW() "
                f"WHERE name = '{name}' AND entities_id = 0;",
                "INSERT INTO glpi_computers ("
                "entities_id, name, contact, comment, users_id, users_id_tech, "
                "is_deleted, is_dynamic, is_recursive, date_creation, date_mod"
                ") "
                "SELECT 0, "
                f"'{name}', "
                f"'{owner}', "
                f"'{comment}', "
                "@owner_id, @owner_id, 0, 0, 1, NOW(), NOW() "
                "FROM DUAL "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM glpi_computers "
                f"WHERE name = '{name}' AND entities_id = 0"
                ");",
                f"-- owner={owner} platform={platform} location={location} source={source}",
            ]
        )

    statements.extend(
        [
            f"SET @cmdb_category_root_name = '{category_root_name}';",
            f"SET @cmdb_category_root_comment = '{category_root_comment}';",
            "INSERT INTO glpi_softwarecategories ("
            "name, comment, softwarecategories_id, completename, level, ancestors_cache, sons_cache"
            ") "
            "SELECT @cmdb_category_root_name, @cmdb_category_root_comment, 0, @cmdb_category_root_name, 1, NULL, NULL "
            "FROM DUAL "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM glpi_softwarecategories "
            "WHERE name = @cmdb_category_root_name AND softwarecategories_id = 0"
            ");",
            "SET @cmdb_category_root_id = ("
            "SELECT id FROM glpi_softwarecategories "
            "WHERE name = @cmdb_category_root_name AND softwarecategories_id = 0 LIMIT 1"
            ");",
            "UPDATE glpi_softwarecategories SET "
            "comment = @cmdb_category_root_comment, "
            "completename = @cmdb_category_root_name, "
            "level = 1 "
            "WHERE id = @cmdb_category_root_id;",
        ]
    )

    for domain_name in category_domains:
        category_name = sql_escape(domain_display_name(domain_name))
        category_comment = sql_escape(f"CMDB imported software category for {domain_name} workloads")
        statements.extend(
            [
                f"SET @software_category_name = '{category_name}';",
                f"SET @software_category_comment = '{category_comment}';",
                "INSERT INTO glpi_softwarecategories ("
                "name, comment, softwarecategories_id, completename, level, ancestors_cache, sons_cache"
                ") "
                "SELECT @software_category_name, @software_category_comment, @cmdb_category_root_id, "
                "CONCAT(@cmdb_category_root_name, ' > ', @software_category_name), 2, NULL, NULL "
                "FROM DUAL "
                "WHERE @cmdb_category_root_id IS NOT NULL AND NOT EXISTS ("
                "SELECT 1 FROM glpi_softwarecategories "
                "WHERE name = @software_category_name AND softwarecategories_id = @cmdb_category_root_id"
                ");",
                "SET @software_category_id = ("
                "SELECT id FROM glpi_softwarecategories "
                "WHERE name = @software_category_name AND softwarecategories_id = @cmdb_category_root_id LIMIT 1"
                ");",
                "UPDATE glpi_softwarecategories SET "
                "comment = @software_category_comment, "
                "completename = CONCAT(@cmdb_category_root_name, ' > ', @software_category_name), "
                "level = 2 "
                "WHERE id = @software_category_id;",
            ]
        )

    for row in package["applications_review"]:
        name = sql_escape(row["name"])
        domain = sql_escape(row.get("domain") or "")
        category_name = sql_escape(domain_display_name(row.get("domain") or "operations"))
        kind = sql_escape(row.get("kind") or "")
        source = sql_escape(row.get("source") or "")
        recommended_owner = sql_escape(row.get("recommended_owner") or "")
        target_computer = sql_escape(row.get("target_computer") or "")
        target_assignment = sql_escape(row.get("target_assignment") or "")
        software_comment = sql_escape(
            "Imported by CMDB agent\n"
            f"Domain: {row.get('domain') or ''}\n"
            f"Kind: {row.get('kind') or ''}\n"
            f"Source: {row.get('source') or ''}\n"
            f"Recommended owner: {row.get('recommended_owner') or ''}\n"
            f"Target assignment: {row.get('target_assignment') or ''}"
        )
        version_name = sql_escape(DISCOVERED_SOFTWARE_VERSION)
        version_comment = sql_escape(
            "Discovered workload entry\n"
            f"Kind: {row.get('kind') or ''}\n"
            f"Source: {row.get('source') or ''}"
        )
        statements.extend(
            [
                f"SET @software_category_name = '{category_name}';",
                "SET @software_category_id = ("
                "SELECT id FROM glpi_softwarecategories "
                "WHERE name = @software_category_name AND softwarecategories_id = @cmdb_category_root_id LIMIT 1"
                ");",
                f"SET @software_name = '{name}';",
                f"SET @software_comment = '{software_comment}';",
                "UPDATE glpi_softwares SET "
                "comment = @software_comment, "
                "is_recursive = 1, "
                "users_id = 0, "
                "users_id_tech = 0, "
                "is_update = 0, "
                "softwares_id = 0, "
                "manufacturers_id = 0, "
                "is_deleted = 0, "
                "is_template = 0, "
                "is_helpdesk_visible = 1, "
                "softwarecategories_id = COALESCE(@software_category_id, 0), "
                "is_valid = 1, "
                "date_mod = NOW() "
                "WHERE name = @software_name AND entities_id = 0;",
                "INSERT INTO glpi_softwares ("
                "entities_id, is_recursive, name, comment, locations_id, users_id_tech, "
                "is_update, softwares_id, manufacturers_id, is_deleted, is_template, "
                "date_mod, users_id, ticket_tco, is_helpdesk_visible, softwarecategories_id, "
                "is_valid, date_creation"
                ") "
                "SELECT 0, 1, @software_name, @software_comment, 0, 0, 0, 0, 0, 0, 0, "
                "NOW(), 0, 0.0000, 1, COALESCE(@software_category_id, 0), 1, NOW() "
                "FROM DUAL "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM glpi_softwares "
                "WHERE name = @software_name AND entities_id = 0"
                ");",
                "SET @software_id = (SELECT id FROM glpi_softwares WHERE name = @software_name AND entities_id = 0 LIMIT 1);",
                f"SET @software_version_name = '{version_name}';",
                f"SET @software_version_comment = '{version_comment}';",
                "UPDATE glpi_softwareversions SET "
                "comment = @software_version_comment, "
                "date_mod = NOW() "
                "WHERE softwares_id = @software_id AND name = @software_version_name AND entities_id = 0;",
                "INSERT INTO glpi_softwareversions ("
                "entities_id, is_recursive, softwares_id, states_id, name, arch, comment, "
                "operatingsystems_id, date_mod, date_creation"
                ") "
                "SELECT 0, 1, @software_id, 0, @software_version_name, '', @software_version_comment, 0, NOW(), NOW() "
                "FROM DUAL "
                "WHERE @software_id IS NOT NULL AND NOT EXISTS ("
                "SELECT 1 FROM glpi_softwareversions "
                "WHERE softwares_id = @software_id AND name = @software_version_name AND entities_id = 0"
                ");",
                "SET @softwareversion_id = ("
                "SELECT id FROM glpi_softwareversions "
                "WHERE softwares_id = @software_id AND name = @software_version_name AND entities_id = 0 LIMIT 1"
                ");",
            ]
        )
        if target_computer:
            statements.extend(
                [
                    f"SET @computer_name = '{target_computer}';",
                    "SET @computer_id = (SELECT id FROM glpi_computers WHERE name = @computer_name AND entities_id = 0 LIMIT 1);",
                    "UPDATE glpi_items_softwareversions SET "
                    "is_deleted_item = 0, "
                    "is_template_item = 0, "
                    "entities_id = 0, "
                    "is_deleted = 0, "
                    "is_dynamic = 0 "
                    "WHERE itemtype = 'Computer' AND items_id = @computer_id AND softwareversions_id = @softwareversion_id;",
                    "INSERT INTO glpi_items_softwareversions ("
                    "items_id, itemtype, softwareversions_id, is_deleted_item, is_template_item, "
                    "entities_id, is_deleted, is_dynamic, date_install"
                    ") "
                    "SELECT @computer_id, 'Computer', @softwareversion_id, 0, 0, 0, 0, 0, NULL "
                    "FROM DUAL "
                    "WHERE @computer_id IS NOT NULL AND @softwareversion_id IS NOT NULL AND NOT EXISTS ("
                    "SELECT 1 FROM glpi_items_softwareversions "
                    "WHERE itemtype = 'Computer' AND items_id = @computer_id AND softwareversions_id = @softwareversion_id"
                    ");",
                    f"-- software={name} domain={domain} kind={kind} source={source} recommended_owner={recommended_owner} target={target_computer} assignment={target_assignment}",
                ]
            )
        else:
            statements.append(
                f"-- software={name} domain={domain} kind={kind} source={source} recommended_owner={recommended_owner} target=unassigned assignment={target_assignment}"
            )

    statements.extend(
        [
            "COMMIT;",
            "SELECT COUNT(*) AS computers_count FROM glpi_computers;",
            "SELECT COUNT(*) AS softwarecategories_count FROM glpi_softwarecategories;",
            "SELECT COUNT(*) AS softwares_count FROM glpi_softwares;",
            "SELECT COUNT(*) AS softwareversions_count FROM glpi_softwareversions;",
            "SELECT COUNT(*) AS software_links_count FROM glpi_items_softwareversions;",
        ]
    )
    if computer_names:
        names_sql = ", ".join(f"'{name}'" for name in sorted(set(computer_names)))
        statements.append(
            "SELECT id, name, contact, users_id, users_id_tech "
            "FROM glpi_computers "
            f"WHERE name IN ({names_sql}) "
            "ORDER BY id ASC;"
        )
    return "\n".join(statements) + "\n"


def read_env_values(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        raise FileNotFoundError(f"Env file not found: {env_file}")
    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def discover_glpi_db_container() -> str:
    if shutil.which("docker") is None:
        raise RuntimeError("docker is not available in PATH for GLPI apply execution")
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.service=glpi-db",
            "--format",
            "{{.Names}}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Unable to discover GLPI DB container: {result.stderr.strip()}")
    name = result.stdout.strip().splitlines()
    if not name:
        raise RuntimeError("GLPI database container not found")
    return name[0]


def build_netbox_manage_shell_script(package: dict[str, Any]) -> str:
    payload = json.dumps(package, ensure_ascii=True)
    return f"""import json
from ipaddress import ip_address
from django.utils.text import slugify
from dcim.choices import DeviceStatusChoices, InterfaceTypeChoices
from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Interface,
    InventoryItem,
    InventoryItemRole,
    Manufacturer,
    Platform,
    Site,
)
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress, Prefix

payload = json.loads(r'''{payload}''')
DOMAIN_COLORS = {json.dumps(DOMAIN_COLORS, ensure_ascii=True)}
summary = {{
    "site": payload["site"]["name"],
    "created": {{}},
    "updated": {{}},
    "counts": {{
        "devices": len(payload["devices"]),
        "interfaces": len(payload["interfaces"]),
        "ip_addresses": len(payload["ip_addresses"]),
        "prefixes": len(payload["prefixes"]),
        "inventory_items": len([item for item in payload["service_candidates"] if item.get("target_device")]),
        "inventory_item_roles": len({{(item.get("domain") or "operations") for item in payload["service_candidates"] if item.get("target_device")}}),
        "service_candidates_review_required": len([item for item in payload["service_candidates"] if item.get("review_required")]),
    }},
}}

def bump(bucket, key):
    bucket[key] = bucket.get(key, 0) + 1

def resolve_ip_address(item, device):
    raw_value = str(item.get("primary_ip4_raw") or "").strip()
    if not item.get("primary_ip4_was_assumed") or not raw_value:
        return item["primary_ip4"]

    existing_primary = getattr(device.primary_ip4, "address", None)
    if existing_primary and str(existing_primary).split("/")[0] == raw_value:
        return str(existing_primary)

    candidates = [
        ip
        for ip in IPAddress.objects.all()
        if str(ip.address).split("/")[0] == raw_value
    ]
    if candidates:
        candidates.sort(key=lambda ip: ip.address.prefixlen)
        return str(candidates[0].address)

    for prefix in Prefix.objects.all():
        network = prefix.prefix
        if ip_address(raw_value) in network:
            return f"{{raw_value}}/{{network.prefixlen}}"

    return item["primary_ip4"]

def inventory_role_name(domain):
    normalized = (domain or "operations").strip() or "operations"
    return f"{{normalized}}-service"

site_data = payload["site"]
site, created = Site.objects.get_or_create(
    name=site_data["name"],
    defaults={{"slug": site_data["slug"]}},
)
bump(summary["created"] if created else summary["updated"], "sites")
if not created:
    if site.slug != site_data["slug"]:
        site.slug = site_data["slug"]
        site.save()

manufacturers = {{}}
for item in payload["manufacturers"]:
    obj, created = Manufacturer.objects.get_or_create(
        name=item["name"],
        defaults={{"slug": item["slug"]}},
    )
    manufacturers[item["name"]] = obj
    bump(summary["created"] if created else summary["updated"], "manufacturers")
    if not created and obj.slug != item["slug"]:
        obj.slug = item["slug"]
        obj.save()

roles = {{}}
for item in payload["device_roles"]:
    obj, created = DeviceRole.objects.get_or_create(
        name=item["name"],
        defaults={{"slug": item["slug"], "color": item["color"]}},
    )
    roles[item["name"]] = obj
    bump(summary["created"] if created else summary["updated"], "device_roles")
    if not created:
        changed = False
        if obj.slug != item["slug"]:
            obj.slug = item["slug"]
            changed = True
        if obj.color != item["color"]:
            obj.color = item["color"]
            changed = True
        if changed:
            obj.save()

platforms = {{}}
for item in payload["platforms"]:
    obj, created = Platform.objects.get_or_create(
        name=item["name"],
        defaults={{"slug": item["slug"]}},
    )
    platforms[item["name"]] = obj
    bump(summary["created"] if created else summary["updated"], "platforms")
    if not created and obj.slug != item["slug"]:
        obj.slug = item["slug"]
        obj.save()

device_types = {{}}
for item in payload["device_types"]:
    manufacturer = manufacturers[item["manufacturer"]]
    obj, created = DeviceType.objects.get_or_create(
        model=item["model"],
        manufacturer=manufacturer,
        defaults={{
            "slug": item["slug"],
            "u_height": item.get("u_height", 1),
            "is_full_depth": item.get("is_full_depth", False),
        }},
    )
    device_types[item["model"]] = obj
    bump(summary["created"] if created else summary["updated"], "device_types")
    if not created:
        changed = False
        if obj.slug != item["slug"]:
            obj.slug = item["slug"]
            changed = True
        if obj.u_height != item.get("u_height", 1):
            obj.u_height = item.get("u_height", 1)
            changed = True
        if obj.is_full_depth != item.get("is_full_depth", False):
            obj.is_full_depth = item.get("is_full_depth", False)
            changed = True
        if changed:
            obj.save()

prefixes = {{}}
for item in payload["prefixes"]:
    obj, created = Prefix.objects.get_or_create(
        prefix=item["prefix"],
        defaults={{"status": item.get("status", "active")}},
    )
    prefixes[item["prefix"]] = obj
    bump(summary["created"] if created else summary["updated"], "prefixes")
    if not created and obj.status != item.get("status", "active"):
        obj.status = item.get("status", "active")
        obj.save()

devices = {{}}
for item in payload["devices"]:
    role = roles[item["role"]]
    platform = platforms[item["platform"]]
    device_type = device_types[item["device_type"]]
    obj, created = Device.objects.get_or_create(
        name=item["name"],
        defaults={{
            "device_type": device_type,
            "role": role,
            "site": site,
            "platform": platform,
            "status": DeviceStatusChoices.STATUS_ACTIVE,
        }},
    )
    bump(summary["created"] if created else summary["updated"], "devices")
    if not created:
        obj.device_type = device_type
        obj.role = role
        obj.site = site
        obj.platform = platform
        obj.status = DeviceStatusChoices.STATUS_ACTIVE
        obj.save()
    devices[item["name"]] = obj

interfaces = {{}}
for item in payload["interfaces"]:
    device = devices[item["device"]]
    obj, created = Interface.objects.get_or_create(
        device=device,
        name=item["name"],
        defaults={{"type": InterfaceTypeChoices.TYPE_VIRTUAL}},
    )
    bump(summary["created"] if created else summary["updated"], "interfaces")
    if not created and obj.type != InterfaceTypeChoices.TYPE_VIRTUAL:
        obj.type = InterfaceTypeChoices.TYPE_VIRTUAL
        obj.save()
    interfaces[(item["device"], item["name"])] = obj

for item in payload["ip_addresses"]:
    device = devices[item["assigned_device"]]
    package_device = next(
        candidate for candidate in payload["devices"] if candidate["name"] == item["assigned_device"]
    )
    resolved_address = resolve_ip_address(package_device, device)
    obj, created = IPAddress.objects.get_or_create(
        address=resolved_address,
        defaults={{"status": IPAddressStatusChoices.STATUS_ACTIVE}},
    )
    bump(summary["created"] if created else summary["updated"], "ip_addresses")
    iface = interfaces[(item["assigned_device"], item["assigned_interface"])]
    obj.status = IPAddressStatusChoices.STATUS_ACTIVE
    obj.assigned_object = iface
    obj.save()
    if str(getattr(device.primary_ip4, "address", "")) != resolved_address:
        device.primary_ip4 = obj
        device.save()

inventory_roles = {{}}
for item in payload["service_candidates"]:
    target_device = item.get("target_device")
    if not target_device:
        continue
    domain = item.get("domain") or "operations"
    role_name = inventory_role_name(domain)
    role_slug = slugify(role_name)
    role_description = f"Discovered {{domain}} workload inventory imported by the CMDB agent."
    obj, created = InventoryItemRole.objects.get_or_create(
        name=role_name,
        defaults={{
            "slug": role_slug,
            "description": role_description,
            "color": DOMAIN_COLORS.get(domain, "9e9e9e"),
        }},
    )
    inventory_roles[domain] = obj
    bump(summary["created"] if created else summary["updated"], "inventory_item_roles")
    if not created:
        changed = False
        expected_color = DOMAIN_COLORS.get(domain, "9e9e9e")
        if obj.slug != role_slug:
            obj.slug = role_slug
            changed = True
        if obj.description != role_description:
            obj.description = role_description
            changed = True
        if obj.color != expected_color:
            obj.color = expected_color
            changed = True
        if changed:
            obj.save()

for item in payload["service_candidates"]:
    target_device = item.get("target_device")
    if not target_device:
        continue
    device = devices[target_device]
    domain = item.get("domain") or "operations"
    label = item.get("kind") or ""
    part_id = item.get("kind") or ""
    description = f"Discovered {{item.get('kind') or 'service'}} workload from {{item.get('source') or 'unknown source'}}"
    role = inventory_roles.get(domain)
    obj, created = InventoryItem.objects.get_or_create(
        device=device,
        name=item["name"],
        defaults={{
            "label": label,
            "description": description,
            "status": "active",
            "role": role,
            "part_id": part_id,
            "discovered": True,
        }},
    )
    bump(summary["created"] if created else summary["updated"], "inventory_items")
    if not created:
        changed = False
        if obj.label != label:
            obj.label = label
            changed = True
        if obj.description != description:
            obj.description = description
            changed = True
        if obj.status != "active":
            obj.status = "active"
            changed = True
        expected_role_id = role.pk if role else None
        if obj.role_id != expected_role_id:
            obj.role = role
            changed = True
        if obj.part_id != part_id:
            obj.part_id = part_id
            changed = True
        if not obj.discovered:
            obj.discovered = True
            changed = True
        if changed:
            obj.save()

print(json.dumps(summary))
"""


class NetBoxPackageApplier:
    def __init__(self, package_path: Path, container_name: str = "cmdb-netbox") -> None:
        self.package_path = package_path.resolve()
        self.container_name = container_name

    def load_package(self) -> dict[str, Any]:
        return load_json_file(self.package_path)

    def build_plan(self) -> dict[str, Any]:
        return build_netbox_apply_plan(self.load_package(), container_name=self.container_name)

    def apply(self, dry_run: bool = True) -> dict[str, Any]:
        package = self.load_package()
        plan = build_netbox_apply_plan(package, container_name=self.container_name)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "package_path": str(self.package_path),
                "container_name": self.container_name,
                "plan": plan,
            }

        if shutil.which("docker") is None:
            raise RuntimeError("docker is not available in PATH for NetBox apply execution")

        script = build_netbox_manage_shell_script(package)
        command = [
            "docker",
            "exec",
            "-i",
            self.container_name,
            "/opt/netbox/venv/bin/python3",
            "/opt/netbox/netbox/manage.py",
            "shell",
        ]
        result = subprocess.run(
            command,
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"NetBox apply failed for container {self.container_name}: {result.stderr.strip() or result.stdout.strip()}"
            )

        execution = None
        for line in reversed(result.stdout.splitlines()):
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                execution = json.loads(stripped)
                break
        if execution is None:
            raise RuntimeError("NetBox apply completed without JSON execution summary")

        return {
            "ok": True,
            "dry_run": False,
            "package_path": str(self.package_path),
            "container_name": self.container_name,
            "plan": plan,
            "execution": execution,
        }


class GLPIPackageApplier:
    def __init__(
        self,
        package_path: Path,
        env_file: Path = REPO_ROOT / "deploy/cmdb/.env",
        db_container: str | None = None,
    ) -> None:
        self.package_path = package_path.resolve()
        self.env_file = env_file.resolve()
        self.db_container = db_container

    def load_package(self) -> dict[str, Any]:
        return load_json_file(self.package_path)

    def build_plan(self) -> dict[str, Any]:
        return build_glpi_apply_plan(self.load_package())

    def apply(self, dry_run: bool = True) -> dict[str, Any]:
        package = self.load_package()
        plan = build_glpi_apply_plan(package)
        sql_script = build_glpi_sql_script(package)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "package_path": str(self.package_path),
                "env_file": str(self.env_file),
                "db_container": self.db_container,
                "plan": plan,
                "sql_preview": sql_script,
            }

        env_values = read_env_values(self.env_file)
        db_user = env_values.get("GLPI_DB_USER")
        db_password = env_values.get("GLPI_DB_PASSWORD")
        db_name = env_values.get("GLPI_DB_NAME")
        if not db_user or not db_password or not db_name:
            raise RuntimeError(f"Missing GLPI DB credentials in env file: {self.env_file}")

        container_name = self.db_container or discover_glpi_db_container()
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container_name,
                "mariadb",
                f"-u{db_user}",
                f"-p{db_password}",
                db_name,
            ],
            input=sql_script,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"GLPI apply failed for container {container_name}: {result.stderr.strip() or result.stdout.strip()}"
            )
        return {
            "ok": True,
            "dry_run": False,
            "package_path": str(self.package_path),
            "env_file": str(self.env_file),
            "db_container": container_name,
            "plan": plan,
            "execution_output": result.stdout.strip(),
        }


@router.get("/health")
async def cmdb_agent_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "cmdb-agent",
        "defaults": {
            "repo_root": str(REPO_ROOT),
            "inventory_file": str(DEFAULT_INVENTORY),
            "output_dir": str(DEFAULT_OUTPUT_DIR),
            "overrides_file": str(REPO_ROOT / DEFAULT_OVERRIDES_RELATIVE_PATH),
        },
    }


def _cmdb_v2():
    """Retorna CmdbAgentV2 se CMDB_AGENT_VERSION=v2."""
    if os.getenv("CMDB_AGENT_VERSION", "v1") == "v2":
        from specialized_agents.cmdb_agent_langgraph import get_cmdb_agent_langgraph
        return get_cmdb_agent_langgraph()
    return None


@router.post("/run")
async def cmdb_agent_run(payload: CmdbAgentRunRequest) -> dict[str, Any]:
    if v2 := _cmdb_v2():
        return await v2.run(payload)
    try:
        agent = CmdbLoadAgent(
            repo_root=Path(payload.repo_root) if payload.repo_root else REPO_ROOT,
            inventory_file=Path(payload.inventory_file) if payload.inventory_file else DEFAULT_INVENTORY,
            output_dir=Path(payload.output_dir) if payload.output_dir else DEFAULT_OUTPUT_DIR,
            overrides_file=Path(payload.overrides_file) if payload.overrides_file else None,
            site_name=payload.site_name,
        )
        return agent.run(write_artifacts=payload.write_outputs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - exercised by API smoke coverage
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/apply/netbox")
async def cmdb_agent_apply_netbox(payload: CmdbNetboxApplyRequest) -> dict[str, Any]:
    if v2 := _cmdb_v2():
        return await v2.apply_netbox(payload)
    try:
        return NetBoxPackageApplier(
            package_path=Path(payload.package_path),
            container_name=payload.container_name,
        ).apply(dry_run=payload.dry_run)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/apply/glpi")
async def cmdb_agent_apply_glpi(payload: CmdbGlpiApplyRequest) -> dict[str, Any]:
    if v2 := _cmdb_v2():
        return await v2.apply_glpi(payload)
    try:
        return GLPIPackageApplier(
            package_path=Path(payload.package_path),
            env_file=Path(payload.env_file),
            db_container=payload.db_container,
        ).apply(dry_run=not payload.execute)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--inventory-file", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overrides-file", type=Path, default=None)
    parser.add_argument("--site-name", default="homelab-main")
    parser.add_argument("--no-write", action="store_true", help="Generate the report in memory only")
    parser.add_argument("--apply-netbox-package", type=Path, default=None)
    parser.add_argument("--plan-glpi-package", type=Path, default=None)
    parser.add_argument("--netbox-container", default="cmdb-netbox")
    parser.add_argument("--glpi-env-file", type=Path, default=REPO_ROOT / "deploy/cmdb/.env")
    parser.add_argument("--glpi-db-container", default=None)
    parser.add_argument("--execute", action="store_true", help="Execute the selected apply action instead of dry-run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply_netbox_package:
        result = NetBoxPackageApplier(
            package_path=args.apply_netbox_package,
            container_name=args.netbox_container,
        ).apply(dry_run=not args.execute)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    if args.plan_glpi_package:
        result = GLPIPackageApplier(
            package_path=args.plan_glpi_package,
            env_file=args.glpi_env_file,
            db_container=args.glpi_db_container,
        ).apply(dry_run=not args.execute)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    agent = CmdbLoadAgent(
        repo_root=args.repo_root,
        inventory_file=args.inventory_file,
        output_dir=args.output_dir,
        overrides_file=args.overrides_file,
        site_name=args.site_name,
    )
    result = agent.run(write_artifacts=not args.no_write)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "site_name": result["site_name"],
                "summary": result["summary"],
                "artifacts": result["artifacts"],
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
