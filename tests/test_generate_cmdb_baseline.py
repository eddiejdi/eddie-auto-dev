"""Tests for the CMDB baseline generator."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.cmdb.generate_cmdb_baseline import (
    build_baseline,
    discover_trading_profiles,
    sync_trading_overrides,
    write_outputs,
)


def test_build_baseline_collects_hosts_services_and_compose_entries(tmp_path: Path) -> None:
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
          ansible_user: ops
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "systemd/grafana-selfheal.service").write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
    (repo_root / "docker/docker-compose.monitoring.yml").write_text(
        """
services:
  grafana:
    image: grafana/grafana:latest
  prometheus:
    image: prom/prometheus:latest
""".strip()
        + "\n",
        encoding="utf-8",
    )

    output_dir = repo_root / "deploy/cmdb/bootstrap/generated"
    baseline = build_baseline(repo_root, inventory, output_dir, "homelab-main")

    assert baseline["summary"]["hosts"] == 2
    assert baseline["summary"]["repo_services"] >= 3
    assert any(device["name"] == "homelab" for device in baseline["netbox_devices"])
    assert any(app["name"] == "grafana" for app in baseline["applications_review"])
    assert baseline["summary"]["domains"]["monitoring"] >= 2


def test_build_baseline_includes_manual_service_annotations_not_present_in_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "deploy/cmdb/bootstrap").mkdir(parents=True)

    inventory = repo_root / "config/inventory_homelab.yml"
    inventory.write_text(
        """
all:
  children:
    homelab:
      hosts:
        homelab:
          ansible_host: 192.168.15.2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "deploy/cmdb/bootstrap/cmdb-agent-overrides.json").write_text(
        json.dumps(
            {
                "service_annotations": {
                    "smart-ir-selfheal.service": {
                        "description": "Watchdog do Smart IR.",
                        "candidate_system": "NetBox service model",
                        "status": "disabled",
                        "status_reason": "Interfere nos outros dispositivos IoT.",
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = repo_root / "deploy/cmdb/bootstrap/generated"
    baseline = build_baseline(repo_root, inventory, output_dir, "homelab-main")

    app = next(item for item in baseline["applications_review"] if item["name"] == "smart-ir-selfheal.service")
    annotation = next(item for item in baseline["annotated_services"] if item["name"] == "smart-ir-selfheal.service")

    assert app["candidate_system"] == "NetBox service model"
    assert app["status"] == "disabled"
    assert app["status_reason"] == "Interfere nos outros dispositivos IoT."
    assert annotation["source"] == "deploy/cmdb/bootstrap/cmdb-agent-overrides.json"


def test_discover_trading_profiles_from_configs_and_env_examples(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_dir = repo_root / "btc_trading_agent"
    agent_dir.mkdir(parents=True)
    (repo_root / "config").mkdir()
    (repo_root / "scripts").mkdir()

    (agent_dir / "config_DOGE_USDT_conservative.json").write_text(
        json.dumps(
            {
                "symbol": "DOGE-USDT",
                "dry_run": False,
                "live_mode": True,
                "_doge_live_notes": {"conta": "master TRADE (kucoin/homelab)"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (agent_dir / "DOGE_USDT_conservative.env.example").write_text(
        "METRICS_PORT=9113\nBTC_ENGINE_API_PORT=8523\n",
        encoding="utf-8",
    )
    (repo_root / "scripts/activate_doge_trading_profiles.sh").write_text(
        'PROFILES=("DOGE_USDT_conservative:9113:8523")\n',
        encoding="utf-8",
    )

    instances = discover_trading_profiles(repo_root)
    assert len(instances) == 1
    assert instances[0].instance == "DOGE_USDT_conservative"
    assert instances[0].symbol == "DOGE-USDT"
    assert instances[0].metrics_port == 9113
    assert instances[0].live_mode is True

    changed = sync_trading_overrides(repo_root, instances)
    assert changed is True
    overrides = json.loads(
        (repo_root / "deploy/cmdb/bootstrap/cmdb-agent-overrides.json").read_text(encoding="utf-8")
    )
    agent_key = "crypto-agent@DOGE_USDT_conservative.service"
    assert agent_key in overrides["service_annotations"]
    assert overrides["service_annotations"][agent_key]["auto_generated"] is True
    assert overrides["service_annotations"][agent_key]["metrics_port"] == 9113


def test_build_baseline_includes_trading_instances_section(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_dir = repo_root / "btc_trading_agent"
    agent_dir.mkdir(parents=True)
    (repo_root / "config").mkdir(parents=True)
    inventory = repo_root / "config/inventory_homelab.yml"
    inventory.write_text(
        "all:\n  children:\n    homelab:\n      hosts:\n        homelab:\n          ansible_host: 192.168.15.2\n",
        encoding="utf-8",
    )
    (agent_dir / "config_SOL_USDT_shadow.json").write_text(
        json.dumps({"symbol": "SOL-USDT", "dry_run": False, "live_mode": True}) + "\n",
        encoding="utf-8",
    )
    (agent_dir / "SOL_USDT_shadow.env.example").write_text(
        "METRICS_PORT=9108\nBTC_ENGINE_API_PORT=8518\n",
        encoding="utf-8",
    )

    output_dir = repo_root / "deploy/cmdb/bootstrap/generated"
    baseline = build_baseline(repo_root, inventory, output_dir, "homelab-main")

    assert baseline["summary"]["trading_instances"] >= 1
    assert any(item["symbol"] == "SOL-USDT" for item in baseline["trading_instances"])
    assert any(
        app["name"] == "crypto-agent@SOL_USDT_shadow.service"
        for app in baseline["applications_review"]
    )


def test_write_outputs_materializes_expected_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    inventory = repo_root / "config/inventory_homelab.yml"
    inventory.parent.mkdir(parents=True)
    inventory.write_text("all:\n  children:\n    homelab:\n      hosts:\n        homelab:\n          ansible_host: 192.168.15.2\n", encoding="utf-8")
    output_dir = repo_root / "deploy/cmdb/bootstrap/generated"

    baseline = build_baseline(repo_root, inventory, output_dir, "homelab-main")
    write_outputs(output_dir, baseline)

    expected = {
        "cmdb-baseline.json",
        "cmdb-baseline.md",
        "netbox-devices.csv",
        "glpi-computers.csv",
        "applications-review.csv",
    }
    assert expected.issubset({path.name for path in output_dir.iterdir()})

    payload = json.loads((output_dir / "cmdb-baseline.json").read_text(encoding="utf-8"))
    assert payload["site_name"] == "homelab-main"
