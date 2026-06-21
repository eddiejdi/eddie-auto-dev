from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from specialized_agents.api import app
from specialized_agents.cmdb_agent import (
    CmdbLoadAgent,
    DISCOVERED_SOFTWARE_VERSION,
    GLPIPackageApplier,
    NetBoxPackageApplier,
    build_glpi_sql_script,
    build_netbox_manage_shell_script,
)


def _build_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "systemd").mkdir()
    (repo_root / "docker").mkdir()

    inventory = repo_root / "config/inventory_homelab.yml"
    inventory.write_text(
        """
all:
  children:
    homelab:
      hosts:
        homelab:
          ansible_host: 192.168.15.2
          ansible_user: homelab
        grafana:
          ansible_host: 192.168.15.9
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (repo_root / "systemd/grafana-selfheal.service").write_text(
        "[Service]\nExecStart=/bin/true\n",
        encoding="utf-8",
    )
    (repo_root / "docker/docker-compose.monitoring.yml").write_text(
        """
services:
  grafana:
    image: grafana/grafana:latest
  prometheus:
    image: prom/prometheus:latest
  pihole:
    image: pihole/pihole:latest
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "docker/docker-compose.apps.yml").write_text(
        """
services:
  wikijs:
    image: requarks/wiki:latest
""".strip()
        + "\n",
        encoding="utf-8",
    )

    output_dir = repo_root / "deploy/cmdb/bootstrap/generated"
    return repo_root, inventory, output_dir


def _write_overrides(repo_root: Path) -> Path:
    overrides_path = repo_root / "deploy/cmdb/bootstrap/cmdb-agent-overrides.json"
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.write_text(
        json.dumps(
            {
                "hosts": {
                    "homelab": {
                        "primary_ip4": "192.168.15.2/24",
                        "ansible_user": "homelab",
                    },
                    "grafana": {
                        "primary_ip4": "192.168.15.9/24",
                        "ansible_user": "platform",
                    },
                },
                "defaults": {
                    "target_device": "homelab",
                    "target_computer": "homelab",
                },
                "service_annotations": {
                    "smart-ir-selfheal.service": {
                        "description": "Watchdog do Smart IR.",
                        "candidate_system": "NetBox service model",
                        "status": "disabled",
                        "status_reason": "Interfere nos outros dispositivos IoT.",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return overrides_path


def test_cmdb_load_agent_writes_review_and_load_packages(tmp_path: Path) -> None:
    repo_root, inventory, output_dir = _build_repo(tmp_path)

    result = CmdbLoadAgent(
        repo_root=repo_root,
        inventory_file=inventory,
        output_dir=output_dir,
        site_name="homelab-main",
    ).run(write_artifacts=True)

    assert result["ok"] is True
    assert result["summary"]["hosts"] == 2
    assert result["summary"]["netbox_devices_ready"] == 2
    assert result["summary"]["glpi_computers_ready"] == 2
    assert result["summary"]["review_findings"] >= 2
    assert "cmdb-agent-report.json" in result["artifacts"]
    assert (output_dir / "cmdb-agent-report.json").exists()
    assert (output_dir / "netbox-load-package.json").exists()
    assert (output_dir / "netbox-apply-plan.json").exists()
    assert (output_dir / "glpi-load-package.json").exists()
    assert (output_dir / "glpi-apply-plan.json").exists()
    assert (output_dir / "glpi-apply.sql").exists()
    assert (output_dir / "review-queue.json").exists()

    netbox_payload = json.loads((output_dir / "netbox-load-package.json").read_text(encoding="utf-8"))
    glpi_payload = json.loads((output_dir / "glpi-load-package.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "cmdb-agent-report.json").read_text(encoding="utf-8"))
    netbox_plan = json.loads((output_dir / "netbox-apply-plan.json").read_text(encoding="utf-8"))
    glpi_plan = json.loads((output_dir / "glpi-apply-plan.json").read_text(encoding="utf-8"))

    assert netbox_payload["site"]["slug"] == "homelab-main"
    assert any(item["address"] == "192.168.15.2/32" for item in netbox_payload["ip_addresses"])
    assert any(item["name"] == "grafana" for item in netbox_payload["devices"])
    assert any(item["target_device"] == "homelab" for item in netbox_payload["service_candidates"])
    assert any(item["name"] == "homelab" for item in glpi_payload["computers"])
    assert any(item["target_computer"] == "homelab" for item in glpi_payload["applications_review"])
    assert report_payload["review_summary"]["by_severity"]["info"] >= 1
    homelab_device = next(item for item in netbox_payload["devices"] if item["name"] == "homelab")
    assert homelab_device["primary_ip4_raw"] == "192.168.15.2"
    assert homelab_device["primary_ip4_was_assumed"] is True
    assert netbox_plan["execution_supported"] is True
    assert glpi_plan["execution_supported"] is True
    assert netbox_plan["counts"]["inventory_items"] >= 1
    assert glpi_plan["counts"]["software_links"] >= 1
    assert glpi_plan["counts"]["software_categories"] >= 1


def test_cmdb_load_agent_applies_overrides_and_clears_review_queue(tmp_path: Path) -> None:
    repo_root, inventory, output_dir = _build_repo(tmp_path)
    overrides_file = _write_overrides(repo_root)

    result = CmdbLoadAgent(
        repo_root=repo_root,
        inventory_file=inventory,
        output_dir=output_dir,
        overrides_file=overrides_file,
        site_name="homelab-main",
    ).run(write_artifacts=True)

    netbox_payload = json.loads((output_dir / "netbox-load-package.json").read_text(encoding="utf-8"))
    glpi_payload = json.loads((output_dir / "glpi-load-package.json").read_text(encoding="utf-8"))

    assert result["summary"]["review_findings"] == 0
    assert result["summary"]["review_queue_items"] == 0
    assert any(item["address"] == "192.168.15.2/24" for item in netbox_payload["ip_addresses"])
    assert all(item["target_assignment"] == "override-default" for item in netbox_payload["service_candidates"])
    assert all(item["target_assignment"] == "override-default" for item in glpi_payload["applications_review"])
    assert all(item["review_required"] is False for item in netbox_payload["service_candidates"])
    assert all(item["review_required"] is False for item in glpi_payload["applications_review"])
    smart_ir = next(item for item in netbox_payload["service_candidates"] if item["name"] == "smart-ir-selfheal.service")
    assert smart_ir["status"] == "disabled"
    assert smart_ir["status_reason"] == "Interfere nos outros dispositivos IoT."


def test_glpi_package_applier_dry_run_and_sql_preview(tmp_path: Path) -> None:
    repo_root, inventory, output_dir = _build_repo(tmp_path)
    CmdbLoadAgent(
        repo_root=repo_root,
        inventory_file=inventory,
        output_dir=output_dir,
        site_name="homelab-main",
    ).run(write_artifacts=True)

    package_path = output_dir / "glpi-load-package.json"
    result = GLPIPackageApplier(
        package_path=package_path,
        env_file=repo_root / "deploy/cmdb/.env",
    ).apply(dry_run=True)
    package = json.loads(package_path.read_text(encoding="utf-8"))
    sql_script = build_glpi_sql_script(package)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["plan"]["execution_supported"] is True
    assert "INSERT INTO glpi_computers" in sql_script
    assert "UPDATE glpi_computers" in sql_script
    assert "glpi_softwarecategories" in sql_script
    assert "INSERT INTO glpi_softwares" in sql_script
    assert "INSERT INTO glpi_softwareversions" in sql_script
    assert "INSERT INTO glpi_items_softwareversions" in sql_script
    assert "homelab" in sql_script
    assert "glpi_users" in sql_script
    assert DISCOVERED_SOFTWARE_VERSION in sql_script


def test_netbox_package_applier_dry_run_and_script(tmp_path: Path) -> None:
    repo_root, inventory, output_dir = _build_repo(tmp_path)
    CmdbLoadAgent(
        repo_root=repo_root,
        inventory_file=inventory,
        output_dir=output_dir,
        site_name="homelab-main",
    ).run(write_artifacts=True)

    package_path = output_dir / "netbox-load-package.json"
    result = NetBoxPackageApplier(package_path=package_path, container_name="cmdb-netbox").apply(dry_run=True)
    package = json.loads(package_path.read_text(encoding="utf-8"))
    script = build_netbox_manage_shell_script(package)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["plan"]["counts"]["devices"] == 2
    assert "review_required_devices" in result["plan"]
    assert "preserves an existing wider prefix" in " ".join(result["plan"]["notes"])
    assert "Site.objects.get_or_create" in script
    assert "Device.objects.get_or_create" in script
    assert "IPAddress.objects.get_or_create" in script
    assert "InventoryItemRole.objects.get_or_create" in script
    assert "InventoryItem.objects.get_or_create" in script
    assert "resolve_ip_address" in script


def test_cmdb_agent_health_and_run_endpoints(tmp_path: Path) -> None:
    repo_root, inventory, output_dir = _build_repo(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    health = client.get("/cmdb/agent/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.post(
        "/cmdb/agent/run",
        json={
            "repo_root": str(repo_root),
            "inventory_file": str(inventory),
            "output_dir": str(output_dir),
            "site_name": "homelab-main",
            "write_outputs": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["summary"]["hosts"] == 2
    assert data["summary"]["review_queue_items"] >= 2
    assert "netbox-load-package.json" in data["artifacts"]

    netbox_apply = client.post(
        "/cmdb/agent/apply/netbox",
        json={
            "package_path": str(output_dir / "netbox-load-package.json"),
            "container_name": "cmdb-netbox",
            "dry_run": True,
        },
    )
    assert netbox_apply.status_code == 200
    netbox_data = netbox_apply.json()
    assert netbox_data["dry_run"] is True
    assert netbox_data["plan"]["execution_supported"] is True

    glpi_apply = client.post(
        "/cmdb/agent/apply/glpi",
        json={
            "package_path": str(output_dir / "glpi-load-package.json"),
            "execute": False,
            "env_file": str(repo_root / "deploy/cmdb/.env"),
        },
    )
    assert glpi_apply.status_code == 200
    glpi_data = glpi_apply.json()
    assert glpi_data["plan"]["execution_supported"] is True
    assert "sql_preview" in glpi_data
