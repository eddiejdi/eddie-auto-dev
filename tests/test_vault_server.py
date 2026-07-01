"""Testes do backend local do Homelab Vault."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parent.parent / "scripts" / "vault" / "vault-server.py"
MODULE_NAME = "vault_server"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, str(MODULE_PATH))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_load_storj_status_summarizes_manifest_and_local_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vault_mount = tmp_path / "vault"
    wallet_dir = vault_mount / "keys" / "storj" / "wallet"
    identity_dir = vault_mount / "keys" / "storj" / "identity"
    wallet_dir.mkdir(parents=True)
    identity_dir.mkdir(parents=True)

    manifest = {
        "generatedAt": "2026-06-18T23:59:00Z",
        "wallet": "0x4787E8bA11d9D32f8A51336a1844e663105a7d24",
        "walletFeatures": ["zksync-era"],
        "quicStatus": "OK",
        "currentMonth": {"payout": 15.02},
        "currentMonthExpectations": 23,
        "custody": {"secretMaterialPresent": True, "secretFiles": ["keystore.json"]},
        "nodeIdentity": {"present": True, "files": ["ca.cert", "identity.cert"]},
    }
    (wallet_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (wallet_dir / "keystore.json").write_text("{}", encoding="utf-8")
    (identity_dir / "ca.cert").write_text("cert", encoding="utf-8")
    (identity_dir / "identity.cert").write_text("cert", encoding="utf-8")

    monkeypatch.setattr(MODULE, "VAULT_MOUNT", vault_mount)
    monkeypatch.setattr(MODULE, "STORJ_MANIFEST", wallet_dir / "manifest.json")

    status = MODULE._load_storj_status()

    assert status["configured"] is True
    assert status["wallet"] == manifest["wallet"]
    assert status["zksync_enabled"] is True
    assert status["secret_material_present"] is True
    assert status["secret_files"] == ["keystore.json"]
    assert status["identity_present"] is True
    assert status["identity_files"] == ["ca.cert", "identity.cert"]
    assert status["current_month_payout"] == 15.02
    assert status["current_month_expectations"] == 23


def test_read_json_returns_none_for_invalid_json(tmp_path: Path) -> None:
    invalid_file = tmp_path / "broken.json"
    invalid_file.write_text("{oops", encoding="utf-8")

    assert MODULE._read_json(invalid_file) is None
