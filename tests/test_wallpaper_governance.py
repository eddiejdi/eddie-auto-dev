"""Testes unitarios para a governanca de wallpapers RPA4ALL."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generation" / "wallpaper_governance.py"
SPEC = importlib.util.spec_from_file_location("wallpaper_governance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
wallpaper_governance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wallpaper_governance
SPEC.loader.exec_module(wallpaper_governance)


def _registry_fixture(tmp_path: Path) -> Path:
    registry_path = tmp_path / "site" / "wallpapers" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = {
        "version": 1,
        "managed_url": "https://auth.rpa4all.com/wallpapers/",
        "source_of_truth": "site/wallpapers/registry.json",
        "asset_root": "assets/wallpapers",
        "policy": {
            "approved_model_primary": "phi4-mini:latest",
            "approved_host_primary": "http://192.168.15.2:11434",
            "approved_model_secondary": "qwen3:0.6b",
            "approved_host_secondary": "http://192.168.15.2:11435",
            "rules": ["Toda arte precisa nascer de uma solicitacao registrada."]
        },
        "prompt_template": {
            "objective": "Gerar prompt corporativo padronizado para wallpaper RPA4ALL.",
            "required_fields": ["titulo", "prompt", "negative_prompt", "paleta_hex", "estilo", "nome_arquivo"]
        },
        "assets": [],
        "requests": []
    }
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return registry_path


def _site_fixture(tmp_path: Path) -> tuple[Path, Path]:
    registry_path = _registry_fixture(tmp_path)
    asset_path = tmp_path / "assets" / "wallpapers" / "novo.svg"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text("<svg></svg>\n", encoding="utf-8")

    request_dir = registry_path.parent / "requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    request_file = request_dir / "20260331-teste.json"
    request_file.write_text('{"request_id":"20260331-teste"}\n', encoding="utf-8")

    registry = wallpaper_governance.load_registry(registry_path)
    registry["assets"].append(
        {
            "asset_id": "novo",
            "title": "Novo Wallpaper",
            "status": "approved",
            "file": "assets/wallpapers/novo.svg",
            "request_id": "20260331-teste",
            "managed_by": "qa",
            "created_at": "2026-03-31T18:30:00+00:00",
        }
    )
    wallpaper_governance.save_registry(registry, registry_path)
    return registry_path, asset_path


def test_build_ollama_prompt_respects_policy(tmp_path: Path) -> None:
    """Prompt deve carregar host/modelo primario e contrato de resposta."""
    registry_path = _registry_fixture(tmp_path)
    registry = wallpaper_governance.load_registry(registry_path)
    request = wallpaper_governance.create_request_payload(
        "Wallpaper Conselho",
        "Padronizar fundo executivo",
        "Diretoria",
        "Corporativo, limpo e tecnologico",
    )

    prompt = wallpaper_governance.build_ollama_prompt(request, registry)

    assert "http://192.168.15.2:11434" in prompt
    assert "phi4-mini:latest" in prompt
    assert "Padronizar fundo executivo" in prompt
    assert "titulo, prompt, negative_prompt" in prompt


def test_persist_request_updates_registry_and_creates_file(tmp_path: Path) -> None:
    """Solicitacao deve ir para o registry e gerar arquivo individual."""
    registry_path = _registry_fixture(tmp_path)
    request = wallpaper_governance.create_request_payload(
        "Wallpaper SSO",
        "Criar fundo institucional para portal Authentik",
        "Usuarios internos",
        "Azul, ciano, premium, com IA aplicada",
    )

    output_path = wallpaper_governance.persist_request(request, registry_path)
    updated = wallpaper_governance.load_registry(registry_path)

    assert output_path.exists()
    assert len(updated["requests"]) == 1
    assert updated["requests"][0]["request_id"] == request.request_id
    assert "portal Authentik" in updated["requests"][0]["ollama_prompt"]


def test_register_asset_appends_approved_asset(tmp_path: Path) -> None:
    """Ativo aprovado deve ser anexado ao catalogo central."""
    registry_path = _registry_fixture(tmp_path)

    asset = wallpaper_governance.register_asset(
        file_path="assets/wallpapers/novo.svg",
        title="Novo Wallpaper Institucional",
        request_id="20260331-novo-wallpaper",
        registry_path=registry_path,
        managed_by="qa",
    )
    updated = wallpaper_governance.load_registry(registry_path)

    assert asset["status"] == "approved"
    assert asset["managed_by"] == "qa"
    assert updated["assets"][0]["file"] == "assets/wallpapers/novo.svg"


def test_export_static_site_copies_assets_and_requests(tmp_path: Path) -> None:
    """Exportacao deve gerar bundle autocontido para publicacao."""
    registry_path, _asset_path = _site_fixture(tmp_path)
    output_dir = tmp_path / "dist" / "wallpapers"

    original_root = wallpaper_governance.ROOT_DIR
    original_template = wallpaper_governance.SITE_TEMPLATE_PATH
    try:
        wallpaper_governance.ROOT_DIR = tmp_path
        wallpaper_governance.SITE_TEMPLATE_PATH = registry_path.parent / "index.html"
        wallpaper_governance.SITE_TEMPLATE_PATH.write_text("<html></html>\n", encoding="utf-8")

        exported = wallpaper_governance.export_static_site(
            registry_path=registry_path,
            output_dir=output_dir,
        )
    finally:
        wallpaper_governance.ROOT_DIR = original_root
        wallpaper_governance.SITE_TEMPLATE_PATH = original_template

    published_registry = json.loads((output_dir / "registry.json").read_text(encoding="utf-8"))

    assert exported["asset_count"] == 1
    assert exported["request_count"] == 1
    assert (output_dir / "index.html").exists()
    assert (output_dir / "assets" / "novo.svg").exists()
    assert (output_dir / "requests" / "20260331-teste.json").exists()
    assert published_registry["assets"][0]["published_file"] == "assets/novo.svg"


def test_export_static_site_fails_when_asset_is_missing(tmp_path: Path) -> None:
    """Exportacao deve falhar quando o ativo aprovado nao existe."""
    registry_path = _registry_fixture(tmp_path)
    registry = wallpaper_governance.load_registry(registry_path)
    registry["assets"].append(
        {
            "asset_id": "ausente",
            "title": "Inexistente",
            "status": "approved",
            "file": "assets/wallpapers/inexistente.svg",
            "request_id": "20260331-ausente",
            "managed_by": "qa",
            "created_at": "2026-03-31T18:35:00+00:00",
        }
    )
    wallpaper_governance.save_registry(registry, registry_path)

    original_root = wallpaper_governance.ROOT_DIR
    original_template = wallpaper_governance.SITE_TEMPLATE_PATH
    try:
        wallpaper_governance.ROOT_DIR = tmp_path
        wallpaper_governance.SITE_TEMPLATE_PATH = registry_path.parent / "index.html"
        wallpaper_governance.SITE_TEMPLATE_PATH.write_text("<html></html>\n", encoding="utf-8")

        try:
            wallpaper_governance.export_static_site(
                registry_path=registry_path,
                output_dir=tmp_path / "dist",
            )
        except FileNotFoundError as exc:
            assert "inexistente.svg" in str(exc)
        else:
            raise AssertionError("Era esperado FileNotFoundError para ativo ausente")
    finally:
        wallpaper_governance.ROOT_DIR = original_root
        wallpaper_governance.SITE_TEMPLATE_PATH = original_template
