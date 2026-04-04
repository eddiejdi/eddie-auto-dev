"""Testes unitarios para o modulo de calendario de feriados brasileiros."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generation.wallpaper_calendar import (
    Holiday,
    build_theme_suggestion,
    compute_easter,
    generate_calendar_data,
    get_holidays,
    get_upcoming_holidays,
)


class TestComputeEaster:
    """Valida calculo da Pascoa pelo algoritmo Computus."""

    @pytest.mark.parametrize(
        "year, expected",
        [
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
            (2028, date(2028, 4, 16)),
            (2030, date(2030, 4, 21)),
        ],
    )
    def test_known_easter_dates(self, year: int, expected: date) -> None:
        """Verifica datas conhecidas de Pascoa."""
        assert compute_easter(year) == expected


class TestGetHolidays:
    """Valida listagem de feriados brasileiros."""

    def test_returns_12_holidays(self) -> None:
        """Brasil tem 12 feriados nacionais."""
        holidays = get_holidays(2026)
        assert len(holidays) == 12

    def test_holidays_are_sorted_by_date(self) -> None:
        """Feriados devem estar ordenados cronologicamente."""
        holidays = get_holidays(2026)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)

    def test_all_holidays_in_correct_year(self) -> None:
        """Todos os feriados pertencem ao ano solicitado."""
        for year in (2024, 2025, 2026, 2027):
            holidays = get_holidays(year)
            for h in holidays:
                assert h.date.year == year

    def test_fixed_holidays_dates(self) -> None:
        """Feriados fixos devem ter datas constantes."""
        holidays = {h.slug: h for h in get_holidays(2026)}
        assert holidays["confraternizacao-universal"].date == date(2026, 1, 1)
        assert holidays["tiradentes"].date == date(2026, 4, 21)
        assert holidays["dia-do-trabalho"].date == date(2026, 5, 1)
        assert holidays["independencia-do-brasil"].date == date(2026, 9, 7)
        assert holidays["nossa-senhora-aparecida"].date == date(2026, 10, 12)
        assert holidays["finados"].date == date(2026, 11, 2)
        assert holidays["proclamacao-da-republica"].date == date(2026, 11, 15)
        assert holidays["natal"].date == date(2026, 12, 25)

    def test_movable_holidays_2026(self) -> None:
        """Feriados moveis de 2026 baseados na Pascoa em 5/abr."""
        holidays = {h.slug: h for h in get_holidays(2026)}
        assert holidays["carnaval"].date == date(2026, 2, 17)
        assert holidays["sexta-feira-santa"].date == date(2026, 4, 3)
        assert holidays["pascoa"].date == date(2026, 4, 5)
        assert holidays["corpus-christi"].date == date(2026, 6, 4)

    def test_movable_flag(self) -> None:
        """Feriados moveis devem ter flag movable=True."""
        holidays = get_holidays(2026)
        movable_slugs = {h.slug for h in holidays if h.movable}
        assert movable_slugs == {
            "carnaval",
            "sexta-feira-santa",
            "pascoa",
            "corpus-christi",
        }

    def test_all_have_palette_with_5_colors(self) -> None:
        """Cada feriado deve ter paleta com 5 cores hex."""
        for h in get_holidays(2026):
            assert len(h.palette_hint) == 5
            for color in h.palette_hint:
                assert color.startswith("#")
                assert len(color) == 7

    def test_all_have_style_hint(self) -> None:
        """Cada feriado deve ter sugestao de estilo."""
        for h in get_holidays(2026):
            assert len(h.style_hint) > 5


class TestHoliday:
    """Valida dataclass Holiday."""

    def test_to_dict_serialization(self) -> None:
        """Holiday.to_dict deve gerar dict serializavel em JSON."""
        h = Holiday(
            date=date(2026, 4, 3),
            name="Sexta-feira Santa",
            slug="sexta-feira-santa",
            style_hint="Sereno, reflexivo",
            palette_hint=["#E6E6FA", "#87CEFA", "#78909C", "#4B8C9A", "#04101F"],
            movable=True,
        )
        d = h.to_dict()
        assert d["date"] == "2026-04-03"
        assert d["name"] == "Sexta-feira Santa"
        assert d["movable"] is True
        assert len(d["palette_hint"]) == 5
        # Deve ser serializavel em JSON
        json.dumps(d)

    def test_frozen(self) -> None:
        """Holiday deve ser imutavel."""
        h = Holiday(
            date=date(2026, 1, 1),
            name="Test",
            slug="test",
            style_hint="test",
            palette_hint=["#000000"],
        )
        with pytest.raises(AttributeError):
            h.name = "changed"  # type: ignore[misc]


class TestGetUpcomingHolidays:
    """Valida busca de feriados proximos."""

    def test_returns_holidays_within_range(self) -> None:
        """Deve retornar apenas feriados dentro do periodo."""
        ref = date(2026, 4, 1)
        upcoming = get_upcoming_holidays(reference=ref, days_ahead=30)
        for h in upcoming:
            assert ref <= h.date <= date(2026, 5, 1)

    def test_empty_when_no_holidays_in_range(self) -> None:
        """Deve retornar vazio quando nao ha feriados no periodo."""
        ref = date(2026, 1, 15)
        upcoming = get_upcoming_holidays(reference=ref, days_ahead=10)
        assert upcoming == []

    def test_cross_year_boundary(self) -> None:
        """Deve funcionar quando o range cruza virada de ano."""
        ref = date(2026, 12, 20)
        upcoming = get_upcoming_holidays(reference=ref, days_ahead=30)
        years = {h.date.year for h in upcoming}
        assert 2026 in years or 2027 in years

    def test_includes_today(self) -> None:
        """Feriado no dia de referencia deve ser incluido."""
        ref = date(2026, 4, 3)  # Sexta-feira Santa
        upcoming = get_upcoming_holidays(reference=ref, days_ahead=1)
        slugs = {h.slug for h in upcoming}
        assert "sexta-feira-santa" in slugs

    def test_sorted_by_date(self) -> None:
        """Resultado deve estar ordenado por data."""
        ref = date(2026, 1, 1)
        upcoming = get_upcoming_holidays(reference=ref, days_ahead=365)
        dates = [h.date for h in upcoming]
        assert dates == sorted(dates)


class TestBuildThemeSuggestion:
    """Valida geracao de sugestao de tema."""

    def test_required_fields(self) -> None:
        """Sugestao deve conter todos os campos padrao."""
        h = Holiday(
            date=date(2026, 12, 25),
            name="Natal",
            slug="natal",
            style_hint="Acolhedor, celebrativo",
            palette_hint=["#C62828", "#2E7D32", "#FFD700", "#FFFFFF", "#0A1628"],
        )
        suggestion = build_theme_suggestion(h)
        assert "title" in suggestion
        assert "business_goal" in suggestion
        assert "audience" in suggestion
        assert "style_direction" in suggestion
        assert "palette_hint" in suggestion
        assert "holiday_slug" in suggestion
        assert "holiday_date" in suggestion

    def test_title_includes_year(self) -> None:
        """Titulo deve conter o ano."""
        h = Holiday(
            date=date(2026, 12, 25),
            name="Natal",
            slug="natal",
            style_hint="Acolhedor",
            palette_hint=["#C62828"],
        )
        suggestion = build_theme_suggestion(h)
        assert "2026" in suggestion["title"]
        assert "Natal" in suggestion["title"]

    def test_holiday_date_is_iso(self) -> None:
        """holiday_date deve estar em formato ISO."""
        h = Holiday(
            date=date(2026, 4, 3),
            name="Sexta-feira Santa",
            slug="sexta-feira-santa",
            style_hint="Sereno",
            palette_hint=["#E6E6FA"],
        )
        suggestion = build_theme_suggestion(h)
        assert suggestion["holiday_date"] == "2026-04-03"


class TestGenerateCalendarData:
    """Valida geracao de dados de calendario."""

    def test_returns_list_of_dicts(self) -> None:
        """Deve retornar lista de dicts serializaveis."""
        data = generate_calendar_data(2026)
        assert isinstance(data, list)
        assert len(data) == 12
        for item in data:
            assert isinstance(item, dict)
            json.dumps(item)

    def test_consistent_with_get_holidays(self) -> None:
        """Deve produzir dados consistentes com get_holidays."""
        holidays = get_holidays(2026)
        data = generate_calendar_data(2026)
        assert len(data) == len(holidays)
        for h, d in zip(holidays, data):
            assert d["name"] == h.name
            assert d["date"] == h.date.isoformat()
