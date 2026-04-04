#!/usr/bin/env python3
"""Gerador de artes para campanha marketing RPA4ALL.

Gera imagens para:
- 5 anúncios Meta/Instagram (1080x1080)
- 2 banners Google Display (300x250 e 728x90)
- 1 anúncio LinkedIn (1200x627)
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

OUTPUT = Path("/workspace/eddie-auto-dev/marketing/ads/images")
OUTPUT.mkdir(parents=True, exist_ok=True)

# ─── Fonts ───────────────────────────────────────────────────────────
FONT_BOLD = "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
FONT_MEDIUM = "/usr/share/fonts/truetype/ubuntu/Ubuntu-M.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf"

# ─── Colors ──────────────────────────────────────────────────────────
BG_DARK = (26, 26, 46)        # #1a1a2e
BG_NAVY = (15, 52, 96)        # #0f3460
BG_DEEP = (10, 10, 26)        # #0a0a1a
CYAN = (0, 212, 255)           # #00d4ff
ORANGE = (255, 107, 53)        # #ff6b35
GREEN = (40, 167, 69)          # #28a745
GOLD = (255, 193, 7)           # #ffc107
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 200)
MEDIUM_GRAY = (150, 150, 150)
DIM_GRAY = (100, 100, 100)
DARK_CARD = (30, 30, 55)
GREEN_DARK = (10, 58, 10)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Carrega fonte com tamanho."""
    return ImageFont.truetype(path, size)


def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple, radius: int, fill: tuple) -> None:
    """Desenha retângulo com cantos arredondados."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_gradient_bg(img: Image.Image, color_top: tuple, color_bottom: tuple) -> None:
    """Aplica gradiente vertical."""
    w, h = img.size
    for y in range(h):
        ratio = y / h
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        ImageDraw.Draw(img).line([(0, y), (w, y)], fill=(r, g, b))


def draw_text_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple,
                      fnt: ImageFont.FreeTypeFont, fill: tuple,
                      max_width: int) -> int:
    """Desenha texto com quebra de linha. Retorna Y final."""
    x, y = xy
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=fnt)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=fnt)
        y += (bbox[3] - bbox[1]) + 8
    return y


def draw_logo(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 48) -> None:
    """Desenha logo RPA4ALL."""
    fnt = font(FONT_BOLD, size)
    draw.text((x, y), "RPA", font=fnt, fill=CYAN)
    bbox = draw.textbbox((x, y), "RPA", font=fnt)
    draw.text((bbox[2], y), "4ALL", font=fnt, fill=WHITE)


def draw_glow_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, color: tuple, alpha: int = 40) -> None:
    """Desenha círculo decorativo com glow."""
    for i in range(3):
        r = radius + i * 15
        a = max(10, alpha - i * 12)
        c = (*color[:3], a)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=2)


# ═══════════════════════════════════════════════════════════════════════
# META AD 01 — Diagnóstico Gratuito (Principal)
# ═══════════════════════════════════════════════════════════════════════
def meta_01() -> None:
    """META-01: Diagnóstico de Automação Gratuito — imagem principal."""
    img = Image.new("RGB", (1080, 1080), BG_DARK)
    draw_gradient_bg(img, BG_NAVY, BG_DARK)
    draw = ImageDraw.Draw(img)

    # Decorative circles
    draw_glow_circle(draw, 900, 150, 80, CYAN)
    draw_glow_circle(draw, 180, 900, 60, CYAN)

    # Top badge
    draw_rounded_rect(draw, (300, 80, 780, 130), 25, (*CYAN[:3],))
    draw.text((340, 87), "100% GRATUITO  ·  SEM COMPROMISSO",
              font=font(FONT_BOLD, 24), fill=BG_DARK)

    # Robot icon (text-based)
    draw.text((460, 170), "🤖", font=font(FONT_REGULAR, 100), fill=WHITE)

    # Main text
    draw.text((540, 310), "DIAGNÓSTICO DE", font=font(FONT_BOLD, 52), fill=WHITE, anchor="mt")
    draw.text((540, 375), "AUTOMAÇÃO", font=font(FONT_BOLD, 64), fill=CYAN, anchor="mt")

    # Divider
    draw.line([(340, 460), (740, 460)], fill=CYAN, width=3)

    # Stats
    draw.text((540, 490), "70%", font=font(FONT_BOLD, 100), fill=CYAN, anchor="mt")
    draw.text((540, 600), "menos trabalho manual", font=font(FONT_MEDIUM, 30), fill=LIGHT_GRAY, anchor="mt")

    # Bullet points
    bullets = [
        "🔍  Mapeamento de processos",
        "💰  Estimativa de economia",
        "🗺️  Roadmap personalizado",
    ]
    y = 670
    for b in bullets:
        draw.text((250, y), b, font=font(FONT_REGULAR, 28), fill=LIGHT_GRAY)
        y += 50

    # CTA button
    draw_rounded_rect(draw, (290, 870, 790, 940), 15, CYAN)
    draw.text((540, 885), "AGENDE GRÁTIS — 20 MINUTOS",
              font=font(FONT_BOLD, 30), fill=BG_DARK, anchor="mt")

    # Logo bottom
    draw_logo(draw, 420, 970, 36)

    img.save(OUTPUT / "META-01_diagnostico_principal.png", quality=95)
    print("✅ META-01 salva")


# ═══════════════════════════════════════════════════════════════════════
# META AD 02 — Quanto Tempo Sua Empresa Desperdiça?
# ═══════════════════════════════════════════════════════════════════════
def meta_02() -> None:
    """META-02: Quanto tempo sua empresa desperdiça?"""
    img = Image.new("RGB", (1080, 1080), BG_DARK)
    draw_gradient_bg(img, (15, 15, 40), BG_NAVY)
    draw = ImageDraw.Draw(img)

    draw_glow_circle(draw, 850, 200, 70, ORANGE)

    # Header
    draw.text((540, 80), "QUANTO TEMPO", font=font(FONT_BOLD, 56), fill=WHITE, anchor="mt")
    draw.text((540, 150), "SUA EMPRESA", font=font(FONT_BOLD, 56), fill=WHITE, anchor="mt")
    draw.text((540, 225), "DESPERDIÇA?", font=font(FONT_BOLD, 60), fill=ORANGE, anchor="mt")

    # Bar chart visual
    bars = [
        ("Manual", 80, (180, 60, 60)),
        ("Automático", 25, GREEN),
    ]
    bar_y = 340
    for label, pct, color in bars:
        draw.text((140, bar_y), label, font=font(FONT_MEDIUM, 26), fill=LIGHT_GRAY)
        bar_w = int(pct / 100 * 600)
        draw_rounded_rect(draw, (300, bar_y - 2, 300 + bar_w, bar_y + 38), 8, color)
        draw.text((310 + bar_w, bar_y + 2), f"{pct}%",
                  font=font(FONT_BOLD, 28), fill=color)
        bar_y += 70

    # Separator
    draw.line([(200, 510), (880, 510)], fill=DIM_GRAY, width=1)

    # Text block
    draw.text((540, 540), "30% do tempo da sua equipe",
              font=font(FONT_BOLD, 34), fill=WHITE, anchor="mt")
    draw.text((540, 590), "vai em tarefas que robôs fazem em segundos",
              font=font(FONT_REGULAR, 26), fill=MEDIUM_GRAY, anchor="mt")

    # Process examples
    examples = [
        ("📊", "Processar dados", "automático"),
        ("📧", "Comunicações", "em batch"),
        ("💰", "Custos operacionais", "reduzidos"),
    ]
    y = 660
    for icon, title, sub in examples:
        draw_rounded_rect(draw, (140, y, 940, y + 70), 10, DARK_CARD)
        draw.text((170, y + 12), icon, font=font(FONT_REGULAR, 36), fill=WHITE)
        draw.text((230, y + 18), title, font=font(FONT_MEDIUM, 28), fill=WHITE)
        draw.text((900, y + 20), sub, font=font(FONT_REGULAR, 22), fill=CYAN, anchor="rt")
        y += 85

    # CTA
    draw_rounded_rect(draw, (240, 920, 840, 990), 15, ORANGE)
    draw.text((540, 938), "DIAGNÓSTICO GRATUITO",
              font=font(FONT_BOLD, 32), fill=WHITE, anchor="mt")

    draw_logo(draw, 440, 1010, 30)
    img.save(OUTPUT / "META-02_tempo_desperdicado.png", quality=95)
    print("✅ META-02 salva")


# ═══════════════════════════════════════════════════════════════════════
# META AD 03 — Carrossel Card 1 (sample)
# ═══════════════════════════════════════════════════════════════════════
def meta_03_cards() -> None:
    """META-03: Carrossel — 5 cards 1080x1080."""
    cards_data = [
        ("01", "CONCILIAÇÃO\nBANCÁRIA", "De 2h/dia\npara 5 minutos", "🏦", CYAN),
        ("02", "EMISSÃO\nDE NFs", "99.7% de precisão\nautomática", "📄", GREEN),
        ("03", "RELATÓRIOS\nGERENCIAIS", "Dashboard em\ntempo real", "📊", ORANGE),
        ("04", "ATENDIMENTO\nAO CLIENTE", "Triagem automática\n24/7", "💬", GOLD),
        ("05", "SEU DIAGNÓSTICO\nGRÁTIS", "20 minutos\nPlano personalizado", "🎯", CYAN),
    ]

    for num, title, subtitle, icon, accent in cards_data:
        img = Image.new("RGB", (1080, 1080), BG_DARK)
        draw_gradient_bg(img, BG_DARK, BG_NAVY)
        draw = ImageDraw.Draw(img)

        # Card number
        draw.text((80, 60), f"0{num}" if len(num) == 1 else num,
                  font=font(FONT_BOLD, 140), fill=(*accent, 50))

        # Decorative
        draw_glow_circle(draw, 850, 250, 100, accent)

        # Icon
        draw.text((540, 250), icon, font=font(FONT_REGULAR, 150), fill=WHITE, anchor="mt")

        # Title
        for i, line in enumerate(title.split("\n")):
            draw.text((540, 460 + i * 75), line,
                      font=font(FONT_BOLD, 64), fill=WHITE, anchor="mt")

        # Divider
        y_div = 460 + len(title.split("\n")) * 75 + 20
        draw.line([(380, y_div), (700, y_div)], fill=accent, width=4)

        # Subtitle
        for i, line in enumerate(subtitle.split("\n")):
            draw.text((540, y_div + 30 + i * 45), line,
                      font=font(FONT_MEDIUM, 34), fill=accent, anchor="mt")

        # Bottom bar
        if num == "05":
            draw_rounded_rect(draw, (240, 880, 840, 950), 15, accent)
            draw.text((540, 897), "AGENDAR AGORA",
                      font=font(FONT_BOLD, 34), fill=BG_DARK, anchor="mt")
        else:
            draw.text((540, 910), "Deslize para ver mais  →",
                      font=font(FONT_REGULAR, 26), fill=MEDIUM_GRAY, anchor="mt")

        # Dots navigation
        dot_x = 440
        for d in range(5):
            c = accent if d == int(num) - 1 else DIM_GRAY
            draw.ellipse([dot_x, 970, dot_x + 14, 984], fill=c)
            dot_x += 28

        draw_logo(draw, 440, 1020, 28)
        img.save(OUTPUT / f"META-03_carrossel_card{num}.png", quality=95)

    print("✅ META-03 carrossel (5 cards) salvo")


# ═══════════════════════════════════════════════════════════════════════
# META AD 04 — Remarketing
# ═══════════════════════════════════════════════════════════════════════
def meta_04() -> None:
    """META-04: Remarketing — Ainda pensando?"""
    img = Image.new("RGB", (1080, 1080), BG_DARK)
    draw_gradient_bg(img, BG_DARK, (30, 20, 10))
    draw = ImageDraw.Draw(img)

    draw_glow_circle(draw, 200, 200, 90, GOLD)
    draw_glow_circle(draw, 880, 800, 70, GOLD)

    # Header
    draw.text((540, 100), "AINDA", font=font(FONT_BOLD, 72), fill=WHITE, anchor="mt")
    draw.text((540, 185), "PENSANDO?", font=font(FONT_BOLD, 72), fill=GOLD, anchor="mt")

    draw.text((540, 300), "👋", font=font(FONT_REGULAR, 100), fill=WHITE, anchor="mt")

    draw.text((540, 430), "Você visitou nosso site mas",
              font=font(FONT_REGULAR, 30), fill=LIGHT_GRAY, anchor="mt")
    draw.text((540, 475), "ainda não agendou seu diagnóstico.",
              font=font(FONT_REGULAR, 30), fill=LIGHT_GRAY, anchor="mt")

    # Benefits card
    draw_rounded_rect(draw, (140, 540, 940, 820), 16, DARK_CARD)
    draw.text((180, 560), "🎁  O que você ganha:", font=font(FONT_BOLD, 30), fill=GOLD)
    benefits = [
        "Mapeamento dos seus processos",
        "Estimativa real de economia",
        "Roadmap personalizado",
        "Comparativo manual vs. automático",
    ]
    y = 610
    for b in benefits:
        draw.text((200, y), f"✓  {b}", font=font(FONT_REGULAR, 26), fill=LIGHT_GRAY)
        y += 45

    # Urgency
    draw_rounded_rect(draw, (300, 850, 780, 895), 8, (*GOLD[:3],))
    draw.text((540, 857), "⏰  VAGAS LIMITADAS ESTA SEMANA",
              font=font(FONT_BOLD, 22), fill=BG_DARK, anchor="mt")

    # CTA
    draw_rounded_rect(draw, (240, 920, 840, 990), 15, GOLD)
    draw.text((540, 938), "AGENDAR AGORA — É GRÁTIS",
              font=font(FONT_BOLD, 30), fill=BG_DARK, anchor="mt")

    draw_logo(draw, 440, 1015, 28)
    img.save(OUTPUT / "META-04_remarketing.png", quality=95)
    print("✅ META-04 salva")


# ═══════════════════════════════════════════════════════════════════════
# META AD 05 — Social Proof / Case Real
# ═══════════════════════════════════════════════════════════════════════
def meta_05() -> None:
    """META-05: Case real — Social Proof."""
    img = Image.new("RGB", (1080, 1080), GREEN_DARK)
    draw_gradient_bg(img, GREEN_DARK, (5, 30, 5))
    draw = ImageDraw.Draw(img)

    draw_glow_circle(draw, 900, 150, 80, GREEN)

    # Badge
    draw_rounded_rect(draw, (320, 60, 760, 110), 25, GREEN)
    draw.text((540, 70), "📊  CASE REAL — RESULTADOS",
              font=font(FONT_BOLD, 26), fill=WHITE, anchor="mt")

    # Main stat
    draw.text((540, 170), "-70%", font=font(FONT_BOLD, 140), fill=GREEN, anchor="mt")
    draw.text((540, 330), "trabalho manual", font=font(FONT_MEDIUM, 36), fill=LIGHT_GRAY, anchor="mt")

    # Divider
    draw.line([(300, 390), (780, 390)], fill=GREEN, width=3)

    # Stats grid
    stats = [
        ("Erros", "8% → 0.3%", "↓ 97%"),
        ("Economia", "R$ 8.500", "/mês"),
        ("Tempo", "120h → 36h", "/mês"),
    ]
    y = 420
    for label, value, unit in stats:
        draw_rounded_rect(draw, (140, y, 940, y + 80), 10, (20, 50, 20))
        draw.text((180, y + 22), label, font=font(FONT_REGULAR, 26), fill=MEDIUM_GRAY)
        draw.text((540, y + 18), value, font=font(FONT_BOLD, 34), fill=WHITE, anchor="mt")
        draw.text((900, y + 24), unit, font=font(FONT_MEDIUM, 24), fill=GREEN, anchor="rt")
        y += 100

    # Bottom text
    draw.text((540, 750), "Empresa de Contabilidade",
              font=font(FONT_MEDIUM, 28), fill=MEDIUM_GRAY, anchor="mt")
    draw.text((540, 790), "Automação de lançamentos com OCR + IA",
              font=font(FONT_REGULAR, 24), fill=DIM_GRAY, anchor="mt")

    # Quote
    draw_rounded_rect(draw, (160, 840, 920, 910), 10, (20, 50, 20))
    draw.text((540, 855), '"Equipe focada em análise, não digitação"',
              font=font(FONT_REGULAR, 24), fill=LIGHT_GRAY, anchor="mt")

    # CTA
    draw_rounded_rect(draw, (240, 930, 840, 1000), 15, GREEN)
    draw.text((540, 948), "QUERO RESULTADOS ASSIM",
              font=font(FONT_BOLD, 30), fill=WHITE, anchor="mt")

    draw_logo(draw, 440, 1020, 28)
    img.save(OUTPUT / "META-05_case_real.png", quality=95)
    print("✅ META-05 salva")


# ═══════════════════════════════════════════════════════════════════════
# GOOGLE DISPLAY — 300x250 e 728x90
# ═══════════════════════════════════════════════════════════════════════
def google_display() -> None:
    """Google Display remarketing banners."""
    # 300x250
    img = Image.new("RGB", (300, 250), BG_DARK)
    draw_gradient_bg(img, BG_NAVY, BG_DARK)
    draw = ImageDraw.Draw(img)

    draw.text((150, 15), "RPA4ALL", font=font(FONT_BOLD, 22), fill=CYAN, anchor="mt")
    draw.text((150, 50), "Ainda", font=font(FONT_BOLD, 28), fill=WHITE, anchor="mt")
    draw.text((150, 82), "pensando?", font=font(FONT_BOLD, 28), fill=GOLD, anchor="mt")
    draw.text((150, 125), "Seu diagnóstico", font=font(FONT_REGULAR, 18), fill=LIGHT_GRAY, anchor="mt")
    draw.text((150, 148), "gratuito está esperando", font=font(FONT_REGULAR, 18), fill=LIGHT_GRAY, anchor="mt")
    draw_rounded_rect(draw, (60, 180, 240, 215), 8, CYAN)
    draw.text((150, 187), "AGENDAR AGORA", font=font(FONT_BOLD, 18), fill=BG_DARK, anchor="mt")
    draw.rectangle([0, 0, 299, 249], outline=DIM_GRAY, width=1)

    img.save(OUTPUT / "GADS_display_300x250.png", quality=95)

    # 728x90
    img2 = Image.new("RGB", (728, 90), BG_DARK)
    draw_gradient_bg(img2, BG_NAVY, BG_DARK)
    d2 = ImageDraw.Draw(img2)

    d2.text((20, 20), "RPA4ALL", font=font(FONT_BOLD, 24), fill=CYAN)
    d2.text((160, 12), "Diagnóstico de Automação Gratuito", font=font(FONT_BOLD, 22), fill=WHITE)
    d2.text((160, 45), "Reduza 70% do trabalho manual", font=font(FONT_REGULAR, 18), fill=LIGHT_GRAY)
    draw_rounded_rect(d2, (560, 20, 710, 65), 8, CYAN)
    d2.text((635, 30), "AGENDAR GRÁTIS", font=font(FONT_BOLD, 17), fill=BG_DARK, anchor="mt")
    d2.rectangle([0, 0, 727, 89], outline=DIM_GRAY, width=1)

    img2.save(OUTPUT / "GADS_display_728x90.png", quality=95)
    print("✅ Google Display banners salvos")


# ═══════════════════════════════════════════════════════════════════════
# LINKEDIN — 1200x627
# ═══════════════════════════════════════════════════════════════════════
def linkedin_01() -> None:
    """LinkedIn Sponsored Content — 1200x627."""
    img = Image.new("RGB", (1200, 627), BG_DARK)
    draw_gradient_bg(img, BG_NAVY, BG_DARK)
    draw = ImageDraw.Draw(img)

    draw_glow_circle(draw, 1050, 120, 80, CYAN)
    draw_glow_circle(draw, 150, 500, 60, CYAN)

    # Left side — text
    draw_logo(draw, 80, 50, 38)

    draw.text((80, 130), "Sua empresa ainda depende",
              font=font(FONT_BOLD, 38), fill=WHITE)
    draw.text((80, 180), "de processos manuais?",
              font=font(FONT_BOLD, 38), fill=CYAN)

    draw.text((80, 260), "Empresas que automatizam com IA",
              font=font(FONT_REGULAR, 24), fill=LIGHT_GRAY)
    draw.text((80, 295), "reduzem até 70% do tempo operacional.",
              font=font(FONT_REGULAR, 24), fill=LIGHT_GRAY)

    # Stats boxes
    stats = [
        ("-70%", "trabalho manual", CYAN),
        ("99.7%", "precisão", GREEN),
        ("3x", "mais rápido", ORANGE),
    ]
    x = 80
    for val, label, color in stats:
        draw_rounded_rect(draw, (x, 360, x + 200, 460), 10, DARK_CARD)
        draw.text((x + 100, 370), val, font=font(FONT_BOLD, 40), fill=color, anchor="mt")
        draw.text((x + 100, 420), label, font=font(FONT_REGULAR, 18), fill=MEDIUM_GRAY, anchor="mt")
        x += 220

    # CTA
    draw_rounded_rect(draw, (80, 500, 420, 565), 12, CYAN)
    draw.text((250, 515), "DIAGNÓSTICO GRATUITO",
              font=font(FONT_BOLD, 28), fill=BG_DARK, anchor="mt")

    # Right side — visual (abstract dashboard)
    draw_rounded_rect(draw, (750, 80, 1130, 540), 16, DARK_CARD)
    # Mini dashboard
    draw.text((940, 100), "Dashboard", font=font(FONT_MEDIUM, 22), fill=CYAN, anchor="mt")
    # Fake bars
    bar_colors = [CYAN, GREEN, ORANGE, CYAN, GREEN]
    for i, bc in enumerate(bar_colors):
        bw = [180, 140, 200, 120, 160][i]
        by = 150 + i * 50
        draw_rounded_rect(draw, (790, by, 790 + bw, by + 30), 6, bc)
        draw.text((790 + bw + 15, by + 2), f"{[87, 65, 93, 58, 78][i]}%",
                  font=font(FONT_REGULAR, 20), fill=LIGHT_GRAY)

    # Big number
    draw.text((940, 430), "70%", font=font(FONT_BOLD, 70), fill=GREEN, anchor="mt")
    draw.text((940, 500), "menos manual", font=font(FONT_REGULAR, 18), fill=MEDIUM_GRAY, anchor="mt")

    img.save(OUTPUT / "LINKEDIN-01_sponsored.png", quality=95)
    print("✅ LinkedIn-01 salva")


def linkedin_02() -> None:
    """LinkedIn ABM — Seus concorrentes já automatizam."""
    img = Image.new("RGB", (1200, 627), BG_DARK)
    draw_gradient_bg(img, (20, 10, 30), BG_NAVY)
    draw = ImageDraw.Draw(img)

    draw_logo(draw, 80, 40, 34)

    draw.text((600, 120), "SEUS CONCORRENTES", font=font(FONT_BOLD, 46), fill=WHITE, anchor="mt")
    draw.text((600, 180), "JÁ ESTÃO AUTOMATIZANDO", font=font(FONT_BOLD, 46), fill=ORANGE, anchor="mt")

    # Comparison
    items = [
        ("✅", "NFs em segundos"),
        ("✅", "Relatórios automáticos"),
        ("✅", "Erros reduzidos p/ 0.3%"),
        ("✅", "Economia R$ 8.500/mês"),
    ]
    y = 260
    for icon, text in items:
        draw.text((320, y), f"{icon}  {text}", font=font(FONT_MEDIUM, 30), fill=LIGHT_GRAY)
        y += 55

    # Warning
    draw_rounded_rect(draw, (250, 500, 950, 555), 10, (60, 30, 10))
    draw.text((600, 510), "⚠️  Não fique para trás — agende seu diagnóstico gratuito",
              font=font(FONT_MEDIUM, 24), fill=ORANGE, anchor="mt")

    # CTA
    draw_rounded_rect(draw, (380, 575, 820, 620), 10, ORANGE)
    draw.text((600, 583), "AGENDAR DIAGNÓSTICO GRÁTIS",
              font=font(FONT_BOLD, 26), fill=WHITE, anchor="mt")

    img.save(OUTPUT / "LINKEDIN-02_abm.png", quality=95)
    print("✅ LinkedIn-02 salva")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🎨 Gerando artes da campanha RPA4ALL...\n")
    meta_01()
    meta_02()
    meta_03_cards()
    meta_04()
    meta_05()
    google_display()
    linkedin_01()
    linkedin_02()
    print(f"\n🏁 Todas as imagens salvas em: {OUTPUT}")
    print(f"   Total de arquivos: {len(list(OUTPUT.glob('*.png')))}")
