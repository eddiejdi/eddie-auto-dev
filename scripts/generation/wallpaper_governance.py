#!/usr/bin/env python3
"""Governanca central de wallpapers RPA4ALL.

Mantem a fonte unica de verdade em ``site/wallpapers/registry.json`` e
gera briefs padronizados para o Ollama conforme a politica empresarial.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from scripts.generation.wallpaper_calendar import (
    build_theme_suggestion,
    generate_calendar_data,
    get_holidays,
    get_upcoming_holidays,
)


LOGGER = logging.getLogger("wallpaper-governance")
ROOT_DIR = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT_DIR / "site" / "wallpapers" / "registry.json"
REQUESTS_DIR = ROOT_DIR / "site" / "wallpapers" / "requests"
SITE_TEMPLATE_PATH = ROOT_DIR / "site" / "wallpapers" / "index.html"


@dataclass(slots=True)
class WallpaperRequest:
    """Representa uma solicitacao corporativa de wallpaper."""

    request_id: str
    title: str
    business_goal: str
    audience: str
    style_direction: str
    created_at: str
    status: str = "pending"


def configure_logging(verbose: bool = False) -> None:
    """Configura logging padrao do utilitario."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


def slugify(value: str) -> str:
    """Normaliza texto para um identificador seguro."""
    normalized = []
    for char in value.lower().strip():
        if char.isalnum():
            normalized.append(char)
        elif normalized and normalized[-1] != "-":
            normalized.append("-")
    return "".join(normalized).strip("-") or "wallpaper"


def now_iso() -> str:
    """Retorna timestamp ISO UTC para persistencia."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Carrega registry central de wallpapers."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_registry(data: dict[str, Any], path: Path = REGISTRY_PATH) -> None:
    """Persiste registry central de wallpapers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_repo_path(relative_path: str) -> Path:
    """Resolve um caminho relativo ao repo e valida escape de raiz."""
    candidate = (ROOT_DIR / relative_path).resolve()
    if ROOT_DIR.resolve() not in candidate.parents and candidate != ROOT_DIR.resolve():
        raise ValueError(f"Caminho fora do repositorio: {relative_path}")
    return candidate


def build_request_id(title: str, created_at: str) -> str:
    """Gera identificador unico e legivel para a solicitacao."""
    date_prefix = created_at.split("T", maxsplit=1)[0].replace("-", "")
    return f"{date_prefix}-{slugify(title)}"


def build_ollama_prompt(request: WallpaperRequest, registry: dict[str, Any]) -> str:
    """Monta prompt corporativo padronizado para o Ollama."""
    policy = registry["policy"]
    contract = ", ".join(registry["prompt_template"]["required_fields"])
    return (
        "Voce e o gerador oficial de briefs visuais da RPA4ALL. "
        "Responda apenas em JSON valido. "
        f"Use a politica empresarial com host/modelo primario {policy['approved_host_primary']} / {policy['approved_model_primary']}. "
        "Crie um wallpaper corporativo 4K 16:9. "
        f"Titulo do pedido: {request.title}. "
        f"Objetivo de negocio: {request.business_goal}. "
        f"Publico-alvo: {request.audience}. "
        f"Direcao visual: {request.style_direction}. "
        "A identidade deve transmitir automacao, IA aplicada, confianca, observabilidade e padrao empresarial RPA4ALL. "
        "Nao usar logos de terceiros, nao usar texto pequeno ilegivel, nao usar visual infantil ou promocional. "
        f"Campos obrigatorios da resposta: {contract}."
    )


def create_request_payload(title: str, business_goal: str, audience: str, style_direction: str) -> WallpaperRequest:
    """Cria payload normalizado de solicitacao."""
    created_at = now_iso()
    request_id = build_request_id(title, created_at)
    return WallpaperRequest(
        request_id=request_id,
        title=title.strip(),
        business_goal=business_goal.strip(),
        audience=audience.strip(),
        style_direction=style_direction.strip(),
        created_at=created_at,
    )


def persist_request(request: WallpaperRequest, registry_path: Path = REGISTRY_PATH) -> Path:
    """Registra solicitacao no registry e grava arquivo individual."""
    registry = load_registry(registry_path)
    request_entry = {
        "request_id": request.request_id,
        "title": request.title,
        "business_goal": request.business_goal,
        "audience": request.audience,
        "style_direction": request.style_direction,
        "created_at": request.created_at,
        "status": request.status,
        "ollama_prompt": build_ollama_prompt(request, registry),
    }
    registry.setdefault("requests", []).append(request_entry)
    save_registry(registry, registry_path)

    output_dir = registry_path.parent / "requests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{request.request_id}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(request_entry, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output_path


def register_asset(
    *,
    file_path: str,
    title: str,
    request_id: str,
    registry_path: Path = REGISTRY_PATH,
    managed_by: str = "edenilson",
) -> dict[str, Any]:
    """Adiciona ativo aprovado no registry central."""
    registry = load_registry(registry_path)
    asset_id = slugify(title)
    asset_entry = {
        "asset_id": asset_id,
        "title": title,
        "status": "approved",
        "file": file_path,
        "request_id": request_id,
        "managed_by": managed_by,
        "created_at": now_iso(),
    }
    registry.setdefault("assets", []).append(asset_entry)
    save_registry(registry, registry_path)
    return asset_entry


def export_static_site(
    *,
    registry_path: Path = REGISTRY_PATH,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Exporta bundle estatico pronto para publicacao em /wallpapers/."""
    registry = load_registry(registry_path)
    destination = output_dir or (ROOT_DIR / "artifacts" / "wallpapers-site")

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    shutil.copy2(SITE_TEMPLATE_PATH, destination / "index.html")

    published_registry = json.loads(json.dumps(registry))
    copied_assets = 0
    assets_dir = destination / "assets"
    requests_dir = destination / "requests"

    for asset in published_registry.get("assets", []):
        source_relative = str(asset["file"])
        source_path = resolve_repo_path(source_relative)
        if not source_path.exists():
            raise FileNotFoundError(f"Ativo nao encontrado para exportacao: {source_relative}")

        if source_relative.startswith("assets/wallpapers/"):
            relative_asset_path = Path(source_relative).relative_to("assets/wallpapers")
        else:
            relative_asset_path = Path(source_path.name)

        target_path = assets_dir / relative_asset_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        asset["published_file"] = f"assets/{relative_asset_path.as_posix()}"
        copied_assets += 1

    source_requests_dir = registry_path.parent / "requests"
    copied_requests = 0
    if source_requests_dir.exists():
        for request_file in sorted(source_requests_dir.glob("*.json")):
            requests_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(request_file, requests_dir / request_file.name)
            copied_requests += 1

    save_registry(published_registry, destination / "registry.json")
    return {
        "output_dir": str(destination),
        "asset_count": copied_assets,
        "request_count": copied_requests,
    }


def update_calendar_in_registry(
    year: int,
    registry_path: Path = REGISTRY_PATH,
) -> list[dict]:
    """Atualiza secao de calendario no registry com feriados do ano."""
    registry = load_registry(registry_path)
    calendar_data = generate_calendar_data(year)
    registry.setdefault("calendar", {})[str(year)] = calendar_data
    save_registry(registry, registry_path)
    return calendar_data


def get_theme_suggestions(
    days_ahead: int = 90,
    registry_path: Path = REGISTRY_PATH,
) -> list[dict]:
    """Retorna sugestoes de temas para feriados proximos sem wallpaper."""
    registry = load_registry(registry_path)
    existing_slugs = {
        r.get("holiday_slug", "") for r in registry.get("requests", [])
    }
    upcoming = get_upcoming_holidays(days_ahead=days_ahead)
    suggestions = []
    for holiday in upcoming:
        year_slug = f"{holiday.slug}-{holiday.date.year}"
        if holiday.slug not in existing_slugs and year_slug not in existing_slugs:
            suggestions.append(build_theme_suggestion(holiday))
    return suggestions


def build_parser() -> argparse.ArgumentParser:
    """Cria parser CLI do utilitario."""
    parser = argparse.ArgumentParser(description="Governanca de wallpapers RPA4ALL")
    parser.add_argument("--verbose", action="store_true", help="Habilita logging detalhado")
    subparsers = parser.add_subparsers(dest="command", required=True)

    request_cmd = subparsers.add_parser("request", help="Registra novo pedido ao Ollama")
    request_cmd.add_argument("--title", required=True)
    request_cmd.add_argument("--business-goal", required=True)
    request_cmd.add_argument("--audience", required=True)
    request_cmd.add_argument("--style-direction", required=True)

    asset_cmd = subparsers.add_parser("register-asset", help="Registra ativo aprovado")
    asset_cmd.add_argument("--file", required=True)
    asset_cmd.add_argument("--title", required=True)
    asset_cmd.add_argument("--request-id", required=True)
    asset_cmd.add_argument("--managed-by", default="edenilson")

    export_cmd = subparsers.add_parser("export-site", help="Exporta bundle estatico para publicacao")
    export_cmd.add_argument("--output-dir", default=str(ROOT_DIR / "artifacts" / "wallpapers-site"))

    cal_cmd = subparsers.add_parser("calendar", help="Gera/atualiza calendario de feriados no registry")
    cal_cmd.add_argument("--year", type=int, default=date.today().year, help="Ano do calendario")

    suggest_cmd = subparsers.add_parser("suggest", help="Sugere temas para feriados proximos sem wallpaper")
    suggest_cmd.add_argument("--days-ahead", type=int, default=90, help="Dias a frente para buscar feriados")

    return parser


def main() -> int:
    """Ponto de entrada do utilitario."""
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)

    if args.command == "request":
        request = create_request_payload(
            args.title,
            args.business_goal,
            args.audience,
            args.style_direction,
        )
        output_path = persist_request(request)
        registry = load_registry()
        prompt = build_ollama_prompt(request, registry)
        LOGGER.info("Solicitacao registrada: %s", request.request_id)
        LOGGER.info("Arquivo: %s", output_path)
        LOGGER.info("Prompt Ollama: %s", prompt)
        return 0

    if args.command == "export-site":
        export = export_static_site(output_dir=Path(args.output_dir))
        LOGGER.info("Bundle exportado: %s", export["output_dir"])
        LOGGER.info("Ativos copiados: %s", export["asset_count"])
        LOGGER.info("Requests copiadas: %s", export["request_count"])
        return 0

    if args.command == "calendar":
        calendar_data = update_calendar_in_registry(args.year)
        LOGGER.info("Calendario %d atualizado: %d feriados", args.year, len(calendar_data))
        for h in calendar_data:
            LOGGER.info("  %s — %s", h["date"], h["name"])
        return 0

    if args.command == "suggest":
        suggestions = get_theme_suggestions(days_ahead=args.days_ahead)
        if not suggestions:
            LOGGER.info("Nenhum feriado proximo sem wallpaper nos proximos %d dias.", args.days_ahead)
            return 0
        LOGGER.info("Sugestoes de temas para feriados proximos:")
        for s in suggestions:
            LOGGER.info("  %s (%s) — %s", s["title"], s["holiday_date"], s["style_direction"])
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))
        return 0

    asset = register_asset(
        file_path=args.file,
        title=args.title,
        request_id=args.request_id,
        managed_by=args.managed_by,
    )
    LOGGER.info("Ativo registrado: %s", asset["asset_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())