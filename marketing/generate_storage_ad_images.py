#!/usr/bin/env python3
"""Gerador de imagens de anúncio — Storage Gerenciado RPA4ALL.

Gera criativos para Meta, Google Display e LinkedIn usando Pillow.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).resolve().parent / "ads" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fontes
FONT_DIR = Path("/usr/share/fonts/truetype/ubuntu")
FONT_BOLD = str(FONT_DIR / "Ubuntu-B.ttf")
FONT_MEDIUM = str(FONT_DIR / "Ubuntu-M.ttf")
FONT_REGULAR = str(FONT_DIR / "Ubuntu-R.ttf")
FONT_LIGHT = str(FONT_DIR / "Ubuntu-L.ttf")

# Paleta Storage (mais escura / corporativa)
BG_DARK = (10, 22, 40)
BG_NAVY = (15, 30, 60)
BG_PURPLE = (26, 10, 40)
CYAN = (0, 212, 255)
RED_ALERT = (231, 76, 60)
GREEN = (39, 174, 96)
GOLD = (255, 193, 7)
WHITE = (240, 240, 240)
GRAY = (160, 170, 180)
DARK_CARD = (20, 35, 65)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def draw_gradient_bg(draw: ImageDraw.Draw, w: int, h: int,
                     top: tuple, bottom: tuple) -> None:
    """Gradiente vertical."""
    for y in range(h):
        r = int(top[0] + (bottom[0] - top[0]) * y / h)
        g = int(top[1] + (bottom[1] - top[1]) * y / h)
        b = int(top[2] + (bottom[2] - top[2]) * y / h)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_rounded_rect(draw: ImageDraw.Draw, xy: tuple, radius: int,
                      fill: tuple, outline: tuple = None) -> None:
    """Retângulo com bordas arredondadas."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)


def draw_text_wrapped(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
                      xy: tuple, fill: tuple, max_width: int,
                      line_spacing: int = 8) -> int:
    """Desenha texto com word-wrap. Retorna y final."""
    x, y = xy
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += bbox[3] - bbox[1] + line_spacing
    return y


def draw_logo(draw: ImageDraw.Draw, x: int, y: int, size: int = 36) -> None:
    """Logo RPA4ALL textual."""
    f = _font(FONT_BOLD, size)
    draw.text((x, y), "RPA", font=f, fill=CYAN)
    bbox = draw.textbbox((x, y), "RPA", font=f)
    draw.text((bbox[2], y), "4ALL", font=f, fill=WHITE)


def draw_server_icon(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 80) -> None:
    """Ícone de servidor/storage estilizado."""
    w, h = size, int(size * 1.4)
    x0, y0 = cx - w // 2, cy - h // 2
    for i in range(3):
        ry = y0 + i * (h // 3)
        draw_rounded_rect(draw, (x0, ry, x0 + w, ry + h // 3 - 4),
                          radius=6, fill=DARK_CARD, outline=CYAN)
        # LED indicators
        draw.ellipse((x0 + 8, ry + 8, x0 + 16, ry + 16), fill=GREEN)
        # Horizontal lines (drives)
        for j in range(3):
            lx = x0 + 24 + j * 18
            draw.rectangle((lx, ry + 6, lx + 12, ry + h // 3 - 10), fill=(40, 60, 90))


def draw_shield_icon(draw: ImageDraw.Draw, cx: int, cy: int,
                     size: int = 80, color: tuple = GREEN) -> None:
    """Ícone de escudo/segurança."""
    w = size
    h = int(size * 1.2)
    x0, y0 = cx - w // 2, cy - h // 2
    points = [
        (cx, y0),
        (x0 + w, y0 + h // 4),
        (x0 + w - w // 8, y0 + h * 3 // 4),
        (cx, y0 + h),
        (x0 + w // 8, y0 + h * 3 // 4),
        (x0, y0 + h // 4),
    ]
    draw.polygon(points, fill=color, outline=WHITE)
    # Checkmark inside
    cw = w // 4
    draw.line([(cx - cw, cy), (cx - cw // 3, cy + cw // 2), (cx + cw, cy - cw // 2)],
              fill=WHITE, width=4)


def draw_bar_chart(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                   data: list[tuple], label_font: ImageFont.FreeTypeFont) -> None:
    """Gráfico de barras horizontal."""
    bar_h = h // len(data) - 10
    for i, (label, pct, color) in enumerate(data):
        by = y + i * (bar_h + 10)
        draw.text((x, by + 2), label, font=label_font, fill=WHITE)
        bar_x = x + 140
        bar_w = int((w - 140) * pct)
        draw_rounded_rect(draw, (bar_x, by, bar_x + bar_w, by + bar_h),
                          radius=4, fill=color)
        val_text = f"R${pct * 0.23:.2f}/GB" if pct > 0.5 else f"R${pct * 0.23:.2f}/GB"
        draw.text((bar_x + bar_w + 10, by + 2), val_text, font=label_font, fill=GRAY)


# ═══ META STORAGE ADS ═══════════════════════════════════════════════

def stg_meta_01() -> None:
    """STG-META-01: Storage 10x mais barato."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_DARK, BG_NAVY)

    draw_logo(draw, 50, 40, 38)

    # Server icon
    draw_server_icon(draw, W - 140, 160, 100)

    # Main text
    y = 140
    f_big = _font(FONT_BOLD, 64)
    draw.text((50, y), "STORAGE", font=f_big, fill=WHITE)
    y += 75
    draw.text((50, y), "EMPRESARIAL", font=f_big, fill=CYAN)

    # 10x stat
    y += 120
    f_huge = _font(FONT_BOLD, 140)
    draw.text((50, y), "10x", font=f_huge, fill=CYAN)
    bbox = draw.textbbox((50, y), "10x", font=f_huge)
    f_sub = _font(FONT_MEDIUM, 44)
    draw.text((bbox[2] + 20, y + 30), "MAIS BARATO", font=f_sub, fill=WHITE)
    draw.text((bbox[2] + 20, y + 80), "que cloud", font=f_sub, fill=GRAY)

    # Comparison bars
    y += 220
    draw_rounded_rect(draw, (50, y, W - 50, y + 200), radius=16, fill=DARK_CARD)
    f_bar = _font(FONT_REGULAR, 24)
    f_label = _font(FONT_BOLD, 28)

    # Cloud bar
    draw.text((80, y + 20), "Cloud (AWS/Azure)", font=f_label, fill=WHITE)
    draw_rounded_rect(draw, (80, y + 55, 900, y + 85), radius=6, fill=RED_ALERT)
    draw.text((910, y + 55), "R$ 0,23/GB", font=f_bar, fill=RED_ALERT)

    # LTFS bar
    draw.text((80, y + 110), "LTFS RPA4ALL", font=f_label, fill=CYAN)
    draw_rounded_rect(draw, (80, y + 145, 160, y + 175), radius=6, fill=GREEN)
    draw.text((175, y + 145), "R$ 0,02/GB", font=f_bar, fill=GREEN)

    # Features
    y += 240
    f_feat = _font(FONT_REGULAR, 30)
    features = [
        "TB a Petabytes  |  SLA 4h  |  LGPD Compliant",
        "Portal Self-Service  |  Recuperacao Automatizada",
    ]
    for feat in features:
        draw.text((50, y), feat, font=f_feat, fill=GRAY)
        y += 42

    # CTA
    y += 20
    draw_rounded_rect(draw, (50, y, 520, y + 65), radius=32, fill=CYAN)
    f_cta = _font(FONT_BOLD, 28)
    draw.text((80, y + 16), "AVALIACAO DE CUSTOS GRATIS", font=f_cta, fill=BG_DARK)

    img.save(OUTPUT_DIR / "STG-META-01_storage_10x.png")
    print("[OK] STG-META-01_storage_10x.png")


def stg_meta_02() -> None:
    """STG-META-02: LGPD compliance."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_PURPLE, BG_DARK)

    draw_logo(draw, 50, 40, 38)

    # Shield icon
    draw_shield_icon(draw, W - 130, 160, 100, RED_ALERT)

    # Alert headline
    y = 140
    f_big = _font(FONT_BOLD, 56)
    draw.text((50, y), "LGPD", font=f_big, fill=RED_ALERT)
    y += 70
    f_med = _font(FONT_BOLD, 44)
    draw.text((50, y), "Seus dados estao", font=f_med, fill=WHITE)
    y += 55
    draw.text((50, y), "realmente protegidos?", font=f_med, fill=CYAN)

    # Multa stat
    y += 100
    f_huge = _font(FONT_BOLD, 100)
    draw.text((50, y), "R$ 50M", font=f_huge, fill=RED_ALERT)
    f_sub = _font(FONT_MEDIUM, 32)
    draw.text((50, y + 110), "multa maxima por infracao LGPD", font=f_sub, fill=GRAY)

    # Compliance features card
    y += 190
    draw_rounded_rect(draw, (50, y, W - 50, y + 290), radius=16, fill=DARK_CARD)
    f_item = _font(FONT_REGULAR, 28)
    items = [
        ("Retencao imutavel 12-36 meses", GREEN),
        ("Write protection 30 dias", GREEN),
        ("Redundancia dual-copy", GREEN),
        ("Relatorios de compliance automaticos", GREEN),
        ("Recuperacao garantida via SLA", GREEN),
    ]
    iy = y + 20
    for text, color in items:
        draw.ellipse((80, iy + 8, 96, iy + 24), fill=color)
        draw.text((110, iy), text, font=f_item, fill=WHITE)
        iy += 48

    # CTA
    y += 330
    draw_rounded_rect(draw, (50, y, 580, y + 65), radius=32, fill=RED_ALERT)
    f_cta = _font(FONT_BOLD, 26)
    draw.text((80, y + 18), "CONSULTA LGPD GRATUITA", font=f_cta, fill=WHITE)

    img.save(OUTPUT_DIR / "STG-META-02_lgpd_compliance.png")
    print("[OK] STG-META-02_lgpd_compliance.png")


def stg_meta_03_cards() -> None:
    """STG-META-03: Carrossel 4 cards — motivos para LTFS."""
    W, H = 1080, 1080
    cards_data = [
        {
            "num": "01",
            "titulo": "Custo 10x Menor",
            "subtitulo": "LTFS vs Cloud",
            "stat": "R$0,02",
            "stat_label": "por GB/mes",
            "detail": "Cloud cobra R$0,23/GB.\nLTFS: economia real\npara volumes grandes.",
            "color": CYAN,
        },
        {
            "num": "02",
            "titulo": "LGPD Compliant",
            "subtitulo": "Retencao imutavel",
            "stat": "100%",
            "stat_label": "compliance",
            "detail": "Retencao 12-36 meses.\nWrite protection 30 dias.\nRelatorios automaticos.",
            "color": GREEN,
        },
        {
            "num": "03",
            "titulo": "SLA Garantido",
            "subtitulo": "Recuperacao rapida",
            "stat": "4h",
            "stat_label": "tempo de recuperacao",
            "detail": "Opcoes de 4h, 24h ou 48h.\nRecuperacao automatizada\nvia catalogo PostgreSQL.",
            "color": GOLD,
        },
        {
            "num": "04",
            "titulo": "Portal Self-Service",
            "subtitulo": "Controle total",
            "stat": "24/7",
            "stat_label": "acesso ao portal",
            "detail": "Gerencie contratos,\nusuarios e arquivos.\nIntegracao via API.",
            "color": CYAN,
            "cta": "SOLICITAR AVALIACAO",
        },
    ]

    for card in cards_data:
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        draw_gradient_bg(d, W, H, BG_DARK, BG_NAVY)

        draw_logo(d, 50, 40, 32)

        # Card number
        f_num = _font(FONT_LIGHT, 120)
        d.text((W - 160, 30), card["num"], font=f_num, fill=(40, 55, 80))

        # Title
        y = 160
        f_title = _font(FONT_BOLD, 52)
        d.text((50, y), card["titulo"], font=f_title, fill=card["color"])
        y += 65
        f_sub = _font(FONT_MEDIUM, 30)
        d.text((50, y), card["subtitulo"], font=f_sub, fill=GRAY)

        # Big stat
        y += 80
        f_stat = _font(FONT_BOLD, 160)
        d.text((50, y), card["stat"], font=f_stat, fill=WHITE)
        bbox = d.textbbox((50, y), card["stat"], font=f_stat)
        f_slabel = _font(FONT_REGULAR, 28)
        d.text((50, bbox[3] + 5), card["stat_label"], font=f_slabel, fill=GRAY)

        # Detail card
        y = 620
        draw_rounded_rect(d, (50, y, W - 50, y + 220), radius=16,
                          fill=DARK_CARD, outline=card["color"])
        f_det = _font(FONT_REGULAR, 30)
        dy = y + 30
        for line in card["detail"].split("\n"):
            d.text((80, dy), line, font=f_det, fill=WHITE)
            dy += 42

        # Accent line
        d.rectangle((50, y, 56, y + 220), fill=card["color"])

        # CTA on last card
        if "cta" in card:
            y = 890
            draw_rounded_rect(d, (50, y, 520, y + 65), radius=32, fill=card["color"])
            f_cta = _font(FONT_BOLD, 26)
            d.text((80, y + 18), card["cta"], font=f_cta, fill=BG_DARK)
        else:
            # Pagination dots
            y = 950
            for i in range(4):
                cx = W // 2 - 40 + i * 26
                color = card["color"] if i == int(card["num"]) - 1 else (60, 70, 90)
                d.ellipse((cx, y, cx + 12, y + 12), fill=color)

        # Bottom tagline
        f_tag = _font(FONT_REGULAR, 22)
        d.text((50, H - 50), "STORAGE GERENCIADO  |  rpa4all.com/storage", font=f_tag, fill=GRAY)

        img.save(OUTPUT_DIR / f"STG-META-03_card{card['num']}.png")
        print(f"[OK] STG-META-03_card{card['num']}.png")


def stg_meta_04() -> None:
    """STG-META-04: Remarketing — 50% OFF."""
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_NAVY, BG_DARK)

    draw_logo(draw, 50, 40, 38)

    # Headline
    y = 140
    f_big = _font(FONT_BOLD, 50)
    draw.text((50, y), "AINDA PAGANDO CARO", font=f_big, fill=WHITE)
    y += 60
    draw.text((50, y), "NO CLOUD STORAGE?", font=f_big, fill=GOLD)

    # Discount badge
    y += 120
    # Circle background
    cx, cy, r = 540, y + 120, 140
    for ri in range(r, 0, -1):
        alpha = int(255 * (ri / r))
        c = (int(GOLD[0] * ri / r), int(GOLD[1] * ri / r), int(GOLD[2] * ri / r))
        draw.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=c)
    f_pct = _font(FONT_BOLD, 100)
    f_off = _font(FONT_BOLD, 40)
    draw.text((cx - 90, cy - 60), "50%", font=f_pct, fill=BG_DARK)
    draw.text((cx - 40, cy + 45), "OFF", font=f_off, fill=BG_DARK)

    # Sub text
    y += 280
    f_sub = _font(FONT_MEDIUM, 32)
    draw.text((50, y), "no primeiro mes", font=_font(FONT_BOLD, 36), fill=GOLD)
    y += 50
    draw.text((50, y), "Storage Gerenciado a partir de R$ 950 setup", font=f_sub, fill=WHITE)

    # Stats
    y += 80
    draw_rounded_rect(draw, (50, y, W - 50, y + 130), radius=16, fill=DARK_CARD)
    f_stat = _font(FONT_BOLD, 48)
    f_label = _font(FONT_REGULAR, 20)
    stats = [
        ("R$8.500", "economia/mes"),
        ("10x", "mais barato"),
        ("4h", "SLA recovery"),
    ]
    sx = 100
    for val, label in stats:
        draw.text((sx, y + 20), val, font=f_stat, fill=CYAN)
        draw.text((sx, y + 75), label, font=f_label, fill=GRAY)
        sx += 310

    # CTA
    y += 170
    draw_rounded_rect(draw, (50, y, 480, y + 65), radius=32, fill=GOLD)
    f_cta = _font(FONT_BOLD, 28)
    draw.text((100, y + 16), "OBTER OFERTA AGORA", font=f_cta, fill=BG_DARK)

    img.save(OUTPUT_DIR / "STG-META-04_remarketing_50off.png")
    print("[OK] STG-META-04_remarketing_50off.png")


# ═══ GOOGLE DISPLAY STORAGE ══════════════════════════════════════════

def stg_google_display() -> None:
    """Banners Google Display para Storage."""
    # 300x250 Medium Rectangle
    W, H = 300, 250
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_DARK, BG_NAVY)

    f_logo = _font(FONT_BOLD, 16)
    draw.text((10, 8), "RPA", font=f_logo, fill=CYAN)
    bbox = draw.textbbox((10, 8), "RPA", font=f_logo)
    draw.text((bbox[2], 8), "4ALL", font=f_logo, fill=WHITE)

    f_head = _font(FONT_BOLD, 22)
    draw.text((10, 40), "Storage 10x", font=f_head, fill=WHITE)
    draw.text((10, 65), "mais barato", font=f_head, fill=CYAN)

    f_sub = _font(FONT_REGULAR, 14)
    draw.text((10, 100), "LTFS vs Cloud: economia real", font=f_sub, fill=GRAY)
    draw.text((10, 118), "LGPD  |  SLA 4h  |  Portal", font=f_sub, fill=GRAY)

    f_price = _font(FONT_BOLD, 18)
    draw.text((10, 150), "R$ 0,02/GB", font=f_price, fill=GREEN)
    f_old = _font(FONT_REGULAR, 14)
    draw.text((140, 153), "vs R$0,23", font=f_old, fill=RED_ALERT)

    draw_rounded_rect(draw, (10, H - 50, W - 10, H - 15), radius=8, fill=CYAN)
    f_cta = _font(FONT_BOLD, 16)
    draw.text((50, H - 46), "AVALIAR CUSTOS", font=f_cta, fill=BG_DARK)

    img.save(OUTPUT_DIR / "STG-GADS_display_300x250.png")
    print("[OK] STG-GADS_display_300x250.png")

    # 728x90 Leaderboard
    W, H = 728, 90
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_DARK, BG_NAVY)

    f_logo = _font(FONT_BOLD, 18)
    draw.text((15, 10), "RPA", font=f_logo, fill=CYAN)
    bbox = draw.textbbox((15, 10), "RPA", font=f_logo)
    draw.text((bbox[2], 10), "4ALL", font=f_logo, fill=WHITE)

    f_head = _font(FONT_BOLD, 24)
    draw.text((15, 42), "Storage LTFS", font=f_head, fill=WHITE)

    f_mid = _font(FONT_BOLD, 20)
    draw.text((200, 15), "10x mais barato que cloud", font=f_mid, fill=CYAN)
    f_sub = _font(FONT_REGULAR, 16)
    draw.text((200, 42), "LGPD Compliant  |  SLA 4h  |  Portal Self-Service", font=f_sub, fill=GRAY)
    draw.text((200, 62), "A partir de R$ 0,02/GB", font=f_sub, fill=GREEN)

    draw_rounded_rect(draw, (W - 180, 20, W - 15, 70), radius=8, fill=CYAN)
    f_cta = _font(FONT_BOLD, 16)
    draw.text((W - 168, 36), "AVALIAR CUSTOS", font=f_cta, fill=BG_DARK)

    img.save(OUTPUT_DIR / "STG-GADS_display_728x90.png")
    print("[OK] STG-GADS_display_728x90.png")


# ═══ LINKEDIN STORAGE ADS ════════════════════════════════════════════

def stg_linkedin_01() -> None:
    """STG-LI-01: Cloud 10x mais caro."""
    W, H = 1200, 627
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_DARK, BG_NAVY)

    draw_logo(draw, 40, 30, 34)

    # Left side
    f_head = _font(FONT_BOLD, 46)
    draw.text((40, 100), "Seu cloud storage", font=f_head, fill=WHITE)
    draw.text((40, 150), "custa 10x mais", font=f_head, fill=RED_ALERT)
    draw.text((40, 200), "do que deveria", font=f_head, fill=RED_ALERT)

    f_sub = _font(FONT_REGULAR, 24)
    y = 275
    lines = [
        "De TB a Petabytes com SLA garantido",
        "LGPD compliant — retencao imutavel",
        "Portal self-service para equipes",
        "Recuperacao automatizada em 4h",
        "Setup a partir de R$ 950",
    ]
    for line in lines:
        draw.ellipse((50, y + 6, 64, y + 20), fill=CYAN)
        draw.text((75, y), line, font=f_sub, fill=WHITE)
        y += 36

    # Right side — comparison card
    card_x = 660
    draw_rounded_rect(draw, (card_x, 80, W - 40, H - 80),
                      radius=20, fill=DARK_CARD, outline=CYAN)

    f_card_title = _font(FONT_BOLD, 26)
    draw.text((card_x + 30, 100), "Comparativo de Custo", font=f_card_title, fill=CYAN)

    # Cloud
    y = 150
    f_name = _font(FONT_BOLD, 22)
    f_val = _font(FONT_BOLD, 48)
    f_unit = _font(FONT_REGULAR, 18)
    draw.text((card_x + 30, y), "CLOUD", font=f_name, fill=RED_ALERT)
    draw.text((card_x + 30, y + 30), "R$ 0,23", font=f_val, fill=RED_ALERT)
    draw.text((card_x + 210, y + 55), "/GB", font=f_unit, fill=GRAY)
    draw_rounded_rect(draw, (card_x + 30, y + 90, W - 70, y + 96), radius=3, fill=RED_ALERT)

    # LTFS
    y = 290
    draw.text((card_x + 30, y), "LTFS RPA4ALL", font=f_name, fill=GREEN)
    draw.text((card_x + 30, y + 30), "R$ 0,02", font=f_val, fill=GREEN)
    draw.text((card_x + 210, y + 55), "/GB", font=f_unit, fill=GRAY)
    bar_w = int(480 * 0.09)  # Proportional
    draw_rounded_rect(draw, (card_x + 30, y + 90, card_x + 30 + bar_w, y + 96),
                      radius=3, fill=GREEN)

    # Savings badge
    y = 440
    draw_rounded_rect(draw, (card_x + 30, y, W - 70, y + 60), radius=12, fill=GREEN)
    f_save = _font(FONT_BOLD, 24)
    draw.text((card_x + 60, y + 16), "Economia: ate 91%", font=f_save, fill=WHITE)

    # CTA
    draw_rounded_rect(draw, (40, H - 70, 370, H - 20), radius=24, fill=CYAN)
    f_cta = _font(FONT_BOLD, 22)
    draw.text((70, H - 60), "SOLICITAR AVALIACAO", font=f_cta, fill=BG_DARK)

    img.save(OUTPUT_DIR / "STG-LINKEDIN-01_custo.png")
    print("[OK] STG-LINKEDIN-01_custo.png")


def stg_linkedin_02() -> None:
    """STG-LI-02: LGPD compliance para DPOs."""
    W, H = 1200, 627
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient_bg(draw, W, H, BG_PURPLE, BG_DARK)

    draw_logo(draw, 40, 30, 34)

    # Shield icon
    draw_shield_icon(draw, W - 120, 120, 80, RED_ALERT)

    f_head = _font(FONT_BOLD, 44)
    draw.text((40, 100), "LGPD: retencao de dados", font=f_head, fill=WHITE)
    draw.text((40, 150), "nao pode ser improvisada", font=f_head, fill=RED_ALERT)

    # Checklist
    y = 230
    f_check = _font(FONT_REGULAR, 26)
    checks = [
        "Retencao imutavel com prazo definido?",
        "Write protection automatico?",
        "Relatorios de auditoria sob demanda?",
        "Recovery SLA documentado?",
    ]
    for text in checks:
        draw.ellipse((60, y + 6, 78, y + 24), fill=GREEN)
        draw.text((90, y), text, font=f_check, fill=WHITE)
        y += 42

    # Warning card
    y += 20
    draw_rounded_rect(draw, (40, y, W - 40, y + 80), radius=14, fill=(60, 20, 30))
    f_warn = _font(FONT_BOLD, 24)
    draw.text((70, y + 10), "Se respondeu 'nao' a qualquer item,", font=f_warn, fill=RED_ALERT)
    draw.text((70, y + 42), "seu compliance tem gaps criticos.", font=f_warn, fill=RED_ALERT)

    # CTA
    draw_rounded_rect(draw, (40, H - 70, 380, H - 20), radius=24, fill=RED_ALERT)
    f_cta = _font(FONT_BOLD, 22)
    draw.text((70, H - 60), "AGENDAR CONVERSA", font=f_cta, fill=WHITE)

    # Right side features
    card_x = 680
    draw_rounded_rect(draw, (card_x, 230, W - 40, H - 90), radius=16, fill=DARK_CARD)
    f_feat_title = _font(FONT_BOLD, 22)
    draw.text((card_x + 20, 250), "Storage RPA4ALL resolve:", font=f_feat_title, fill=CYAN)

    f_feat = _font(FONT_REGULAR, 20)
    features = [
        "Retencao imutavel 12-36 meses",
        "Write protection 30 dias",
        "Redundancia dual-copy",
        "Relatorios automaticos",
        "SLA 4h / 24h / 48h",
        "Custo previsivel mensal",
        "Portal self-service",
    ]
    fy = 290
    for feat in features:
        draw.text((card_x + 30, fy), "→ " + feat, font=f_feat, fill=WHITE)
        fy += 32

    img.save(OUTPUT_DIR / "STG-LINKEDIN-02_lgpd.png")
    print("[OK] STG-LINKEDIN-02_lgpd.png")


# ═══ MAIN ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Gerando imagens Storage RPA4ALL ===\n")

    stg_meta_01()
    stg_meta_02()
    stg_meta_03_cards()
    stg_meta_04()
    stg_google_display()
    stg_linkedin_01()
    stg_linkedin_02()

    print(f"\n=== Concluido — imagens em {OUTPUT_DIR} ===")
