#!/usr/bin/env python3
"""Calendario de feriados brasileiros para geracao automatica de wallpapers.

Calcula feriados nacionais fixos e moveis (baseados na Pascoa) para
qualquer ano, gerando sugestoes de tema para o pipeline de wallpapers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass(frozen=True, slots=True)
class Holiday:
    """Representa um feriado brasileiro com metadados para geracao de wallpaper."""

    date: date
    name: str
    slug: str
    style_hint: str
    palette_hint: list[str]
    movable: bool = False

    def to_dict(self) -> dict:
        """Serializa feriado para JSON."""
        return {
            "date": self.date.isoformat(),
            "name": self.name,
            "slug": self.slug,
            "style_hint": self.style_hint,
            "palette_hint": self.palette_hint,
            "movable": self.movable,
        }


def compute_easter(year: int) -> date:
    """Calcula data da Pascoa pelo algoritmo anonimo gregoriano (Computus)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_val = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_val) // 451
    month, day = divmod(h + l_val - 7 * m + 114, 31)
    return date(year, month, day + 1)


def get_holidays(year: int) -> list[Holiday]:
    """Retorna lista de feriados nacionais brasileiros para o ano informado."""
    easter = compute_easter(year)

    holidays = [
        Holiday(
            date=date(year, 1, 1),
            name="Confraternização Universal",
            slug="confraternizacao-universal",
            style_hint="Celebrativo, renovação, esperança, começo de ciclo",
            palette_hint=["#FFD700", "#FFFFFF", "#1E90FF", "#004080", "#0A1929"],
        ),
        Holiday(
            date=easter - timedelta(days=47),
            name="Carnaval",
            slug="carnaval",
            style_hint="Vibrante, alegre, cultural, energia brasileira",
            palette_hint=["#FFD700", "#FF4500", "#8B00FF", "#00CED1", "#1A1A2E"],
            movable=True,
        ),
        Holiday(
            date=easter - timedelta(days=2),
            name="Sexta-feira Santa",
            slug="sexta-feira-santa",
            style_hint="Sereno, reflexivo, solene, paz e respeito",
            palette_hint=["#E6E6FA", "#87CEFA", "#78909C", "#4B8C9A", "#04101F"],
            movable=True,
        ),
        Holiday(
            date=easter,
            name="Páscoa",
            slug="pascoa",
            style_hint="Renovação, esperança, claridade, primavera",
            palette_hint=["#FFFACD", "#98FB98", "#87CEEB", "#DDA0DD", "#1A2A3A"],
            movable=True,
        ),
        Holiday(
            date=date(year, 4, 21),
            name="Tiradentes",
            slug="tiradentes",
            style_hint="Patriótico, histórico, dignidade, liberdade",
            palette_hint=["#009739", "#FFDF00", "#002776", "#FFFFFF", "#0D1B2A"],
        ),
        Holiday(
            date=date(year, 5, 1),
            name="Dia do Trabalho",
            slug="dia-do-trabalho",
            style_hint="Valorização, produtividade, inovação, automação",
            palette_hint=["#FF6B35", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
        ),
        Holiday(
            date=easter + timedelta(days=60),
            name="Corpus Christi",
            slug="corpus-christi",
            style_hint="Institucional, sóbrio, tradição, contemplativo",
            palette_hint=["#C5CAE9", "#7986CB", "#3F51B5", "#1A237E", "#0D1117"],
            movable=True,
        ),
        Holiday(
            date=date(year, 9, 7),
            name="Independência do Brasil",
            slug="independencia-do-brasil",
            style_hint="Patriótico, soberania, verde-amarelo, orgulho nacional",
            palette_hint=["#009739", "#FFDF00", "#002776", "#FFFFFF", "#0B1929"],
        ),
        Holiday(
            date=date(year, 10, 12),
            name="Nossa Senhora Aparecida",
            slug="nossa-senhora-aparecida",
            style_hint="Sereno, devocional, azul celeste, suave e acolhedor",
            palette_hint=["#4FC3F7", "#81D4FA", "#B3E5FC", "#01579B", "#0A1628"],
        ),
        Holiday(
            date=date(year, 11, 2),
            name="Finados",
            slug="finados",
            style_hint="Contemplativo, saudade, respeito, tons sóbrios",
            palette_hint=["#B0BEC5", "#78909C", "#546E7A", "#37474F", "#0D1117"],
        ),
        Holiday(
            date=date(year, 11, 15),
            name="Proclamação da República",
            slug="proclamacao-da-republica",
            style_hint="Institucional, cívico, modernidade, progresso",
            palette_hint=["#009739", "#FFDF00", "#1565C0", "#E0E0E0", "#0D1B2A"],
        ),
        Holiday(
            date=date(year, 12, 25),
            name="Natal",
            slug="natal",
            style_hint="Acolhedor, celebrativo, caloroso, união e generosidade",
            palette_hint=["#C62828", "#2E7D32", "#FFD700", "#FFFFFF", "#0A1628"],
        ),
    ]

    return sorted(holidays, key=lambda h: h.date)


def get_upcoming_holidays(
    reference: Optional[date] = None,
    days_ahead: int = 90,
) -> list[Holiday]:
    """Retorna feriados entre hoje e ``days_ahead`` dias a frente."""
    ref = reference or date.today()
    end = ref + timedelta(days=days_ahead)

    result: list[Holiday] = []
    for year in {ref.year, end.year}:
        for h in get_holidays(year):
            if ref <= h.date <= end:
                result.append(h)

    return sorted(result, key=lambda h: h.date)


def build_theme_suggestion(holiday: Holiday) -> dict:
    """Gera sugestao de tema para wallpaper baseada no feriado."""
    return {
        "title": f"Wallpaper {holiday.name} {holiday.date.year}",
        "business_goal": (
            f"Fundo institucional para area de trabalho no feriado de {holiday.name}, "
            "transmitindo a identidade de automacao e IA da RPA4ALL"
        ),
        "audience": "Colaboradores e usuarios RPA4ALL",
        "style_direction": holiday.style_hint,
        "palette_hint": holiday.palette_hint,
        "holiday_slug": holiday.slug,
        "holiday_date": holiday.date.isoformat(),
    }


def generate_calendar_data(year: int) -> list[dict]:
    """Gera dados de calendario completo para um ano."""
    return [h.to_dict() for h in get_holidays(year)]
