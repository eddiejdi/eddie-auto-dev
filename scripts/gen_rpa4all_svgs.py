#!/usr/bin/env python3
"""Gera artes SVG para o Wiki.js RPA4All — baseado em output do phi4-mini."""
import math


def gear_points(cx: float, cy: float, outer_r: float, inner_r: float, teeth: int) -> str:
    """Calcula pontos de um gear/cog com N dentes usando trigonometria."""
    points: list[str] = []
    for i in range(teeth * 2):
        angle = math.pi * 2 * i / (teeth * 2) - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def gear_svg(cx: float, cy: float, outer_r: float, inner_r: float,
             teeth: int, fill: str, hole_r: float, dot_r: float,
             hole_fill: str = "#fff", dot_fill: str | None = None) -> str:
    """Gera SVG de um gear completo."""
    pts = gear_points(cx, cy, outer_r, inner_r, teeth)
    dot_fill = dot_fill or fill
    return (
        f'<polygon points="{pts}" fill="{fill}"/>\n'
        f'  <circle cx="{cx}" cy="{cy}" r="{hole_r}" fill="{hole_fill}"/>\n'
        f'  <circle cx="{cx}" cy="{cy}" r="{dot_r}" fill="{dot_fill}"/>'
    )


# 1. Favicon (64x64)
favicon = f'''<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  {gear_svg(32, 32, 28, 20, 8, "#1976d2", 12, 4)}
</svg>'''

with open("/tmp/rpa4all_favicon.svg", "w") as f:
    f.write(favicon)
print("Done: favicon")

# 2. Logo (280x60)
logo = f'''<svg viewBox="0 0 280 60" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(5,5)">
    {gear_svg(25, 25, 22, 16, 8, "#1976d2", 10, 3)}
  </g>
  <text x="62" y="32" font-family="Arial, Helvetica, sans-serif" font-weight="bold"
        font-size="28" fill="#263238">RPA4All</text>
  <text x="62" y="50" font-family="Arial, Helvetica, sans-serif"
        font-size="11" fill="#607d8b">Automação Inteligente</text>
</svg>'''

with open("/tmp/rpa4all_logo.svg", "w") as f:
    f.write(logo)
print("Done: logo")

# 3. Banner (1200x200)
banner = f'''<svg viewBox="0 0 1200 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0d47a1"/>
      <stop offset="50%" stop-color="#1565c0"/>
      <stop offset="100%" stop-color="#1976d2"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="200" fill="url(#bg)"/>
  <g transform="translate(80,30)">
    {gear_svg(70, 70, 60, 44, 10, "rgba(255,255,255,0.9)", 28, 10, "rgba(255,255,255,0.15)", "rgba(255,255,255,0.5)")}
  </g>
  <text x="280" y="105" font-family="Arial, Helvetica, sans-serif" font-weight="bold"
        font-size="56" fill="#ffffff">RPA4All Wiki</text>
  <text x="280" y="145" font-family="Arial, Helvetica, sans-serif"
        font-size="22" fill="rgba(255,255,255,0.75)">Documentação e Base de Conhecimento</text>
  <line x1="280" y1="115" x2="850" y2="115" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>
</svg>'''

with open("/tmp/rpa4all_banner.svg", "w") as f:
    f.write(banner)
print("Done: banner")

print("\nTodas as artes geradas em /tmp/rpa4all_*.svg")
