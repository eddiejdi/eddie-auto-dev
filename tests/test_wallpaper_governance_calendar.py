"""Testes unitarios para os comandos calendar e suggest do wallpaper_governance."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generation.wallpaper_governance import (
    get_theme_suggestions,
    update_calendar_in_registry,
    load_registry,
    save_registry,
)


@pytest.fixture()
def tmp_registry(tmp_path: Path) -> Path:
    """Cria registry temporario para testes."""
    registry = {
        "version": 1,
        "managed_url": "https://test.example.com/wallpapers/",
        "source_of_truth": "site/wallpapers/registry.json",
        "asset_root": "assets/wallpapers",
        "policy": {
            "owner": "TEST",
            "approved_model_primary": "phi4-mini:latest",
            "approved_host_primary": "http://localhost:11434",
            "approved_model_secondary": "qwen3:0.6b",
            "approved_host_secondary": "http://localhost:11435",
            "response_contract": "JSON",
            "rules": ["Regra de teste"],
        },
        "prompt_template": {
            "objective": "Teste",
            "required_fields": ["titulo", "prompt", "negative_prompt", "paleta_hex", "estilo", "nome_arquivo"],
        },
        "assets": [],
        "requests": [],
    }
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return reg_path


class TestUpdateCalendarInRegistry:
    """Valida atualizacao de calendario no registry."""

    def test_adds_calendar_section(self, tmp_registry: Path) -> None:
        """Deve adicionar secao calendar ao registry."""
        result = update_calendar_in_registry(2026, registry_path=tmp_registry)
        assert len(result) == 12

        reg = load_registry(tmp_registry)
        assert "calendar" in reg
        assert "2026" in reg["calendar"]
        assert len(reg["calendar"]["2026"]) == 12

    def test_calendar_entries_have_required_fields(self, tmp_registry: Path) -> None:
        """Cada entrada de calendario deve ter campos padrao."""
        result = update_calendar_in_registry(2026, registry_path=tmp_registry)
        for entry in result:
            assert "date" in entry
            assert "name" in entry
            assert "slug" in entry
            assert "style_hint" in entry
            assert "palette_hint" in entry
            assert "movable" in entry

    def test_multiple_years(self, tmp_registry: Path) -> None:
        """Deve suportar multiplos anos no mesmo registry."""
        update_calendar_in_registry(2026, registry_path=tmp_registry)
        update_calendar_in_registry(2027, registry_path=tmp_registry)

        reg = load_registry(tmp_registry)
        assert "2026" in reg["calendar"]
        assert "2027" in reg["calendar"]
        assert len(reg["calendar"]["2026"]) == 12
        assert len(reg["calendar"]["2027"]) == 12

    def test_overwrites_same_year(self, tmp_registry: Path) -> None:
        """Deve sobrescrever calendario do mesmo ano."""
        update_calendar_in_registry(2026, registry_path=tmp_registry)
        update_calendar_in_registry(2026, registry_path=tmp_registry)

        reg = load_registry(tmp_registry)
        assert len(reg["calendar"]["2026"]) == 12


class TestGetThemeSuggestions:
    """Valida sugestoes de tema baseadas no calendario."""

    def test_returns_suggestions_for_upcoming(self, tmp_registry: Path) -> None:
        """Deve sugerir temas para feriados sem wallpaper."""
        from datetime import date

        with patch("scripts.generation.wallpaper_calendar.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            suggestions = get_theme_suggestions(days_ahead=30, registry_path=tmp_registry)

        assert len(suggestions) > 0
        for s in suggestions:
            assert "title" in s
            assert "business_goal" in s
            assert "holiday_slug" in s

    def test_excludes_existing_requests(self, tmp_registry: Path) -> None:
        """Nao deve sugerir temas para feriados que ja tem request."""
        from datetime import date

        reg = load_registry(tmp_registry)
        reg["requests"].append({
            "request_id": "20260403-wallpaper-sexta-feira-santa-2026",
            "title": "Wallpaper Sexta-feira Santa 2026",
            "business_goal": "test",
            "holiday_slug": "sexta-feira-santa",
            "status": "completed",
        })
        save_registry(reg, tmp_registry)

        with patch("scripts.generation.wallpaper_calendar.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            suggestions = get_theme_suggestions(days_ahead=30, registry_path=tmp_registry)

        slugs = {s["holiday_slug"] for s in suggestions}
        assert "sexta-feira-santa" not in slugs

    def test_empty_when_all_covered(self, tmp_registry: Path) -> None:
        """Deve retornar vazio quando todos feriados proximos ja tem wallpaper."""
        from datetime import date

        reg = load_registry(tmp_registry)
        for slug in ["sexta-feira-santa", "pascoa", "tiradentes"]:
            reg["requests"].append({
                "request_id": f"test-{slug}",
                "title": f"Test {slug}",
                "holiday_slug": slug,
                "status": "completed",
            })
        save_registry(reg, tmp_registry)

        with patch("scripts.generation.wallpaper_calendar.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            suggestions = get_theme_suggestions(days_ahead=20, registry_path=tmp_registry)

        assert len(suggestions) == 0

    def test_suggestion_fields_match_request_format(self, tmp_registry: Path) -> None:
        """Sugestoes devem conter campos compativeis com create_request_payload."""
        from datetime import date

        with patch("scripts.generation.wallpaper_calendar.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            suggestions = get_theme_suggestions(days_ahead=30, registry_path=tmp_registry)

        for s in suggestions:
            assert isinstance(s["title"], str)
            assert isinstance(s["business_goal"], str)
            assert isinstance(s["audience"], str)
            assert isinstance(s["style_direction"], str)
            assert isinstance(s["palette_hint"], list)
