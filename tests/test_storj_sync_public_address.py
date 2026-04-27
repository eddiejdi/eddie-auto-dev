"""Testes unitarios para sincronizacao segura do ADDRESS do Storj."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parent.parent
    / "grafana"
    / "exporters"
    / "storj_sync_public_address.py"
)
MODULE_NAME = "storj_sync_public_address"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, str(MODULE_PATH))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sync_public_address_blocks_host_fallback_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Falha de forma segura quando o IP do container nao pode ser resolvido."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text('contact.external-address: "179.93.21.39:28967"\n', encoding="utf-8")

    monkeypatch.setattr(
        MODULE,
        "detect_container_public_ip",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("container ip unavailable")),
    )
    monkeypatch.setattr(MODULE, "detect_public_ip", lambda _urls: "193.176.127.23")

    with pytest.raises(RuntimeError, match="fallback para o host bloqueado"):
        MODULE.sync_public_address("storagenode", str(config_path), 28967)


def test_sync_public_address_allows_explicit_host_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Mantem compatibilidade apenas quando o fallback for pedido explicitamente."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text('contact.external-address: "179.93.21.39:28967"\n', encoding="utf-8")

    monkeypatch.setattr(
        MODULE,
        "detect_container_public_ip",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("container ip unavailable")),
    )
    monkeypatch.setattr(MODULE, "detect_public_ip", lambda _urls: "193.176.127.23")
    monkeypatch.setattr(MODULE, "load_container_inspect", lambda _name: {"Config": {"Env": ["ADDRESS=193.176.127.23:28967"]}})

    address = MODULE.sync_public_address(
        "storagenode",
        str(config_path),
        28967,
        allow_host_fallback=True,
    )

    assert address == "193.176.127.23:28967"
    assert config_path.read_text(encoding="utf-8") == 'contact.external-address: "193.176.127.23:28967"\n'