#!/usr/bin/env python3
"""
Phomemo Q30 BLE Print Helper
Gera imagem de texto e imprime via driver BLE (phomemo-q30-driver).
Projetado para rodar no homelab com bleak instalado.
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

# Adiciona o driver ao path
DRIVER_DIR = Path(__file__).parent / "phomemo-q30-driver"
if DRIVER_DIR.exists():
    sys.path.insert(0, str(DRIVER_DIR))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERRO: Pillow nao instalado. Rode: pip install pillow")
    sys.exit(1)


# Especificacoes da Q30
DENSITY = 8          # pixels/mm
LABEL_WIDTH_MM = 12  # largura do papel
LABEL_WIDTH_PX = LABEL_WIDTH_MM * DENSITY  # 96 pixels
SUPPORTED_LENGTHS = [22, 25, 30, 40, 50, 70]


def _load_font(size: int):
    """Carrega fonte TrueType com fallback."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def create_label_image(
    text: str,
    label_length_mm: int = 50,
    font_size: int = 28,
    align: str = "left",
) -> Image.Image:
    """
    Cria imagem para etiqueta Q30.

    O driver (image_processor.py) espera imagem no formato:
      largura = label_length_px (ex: 400 para 50mm)
      altura  = LABEL_WIDTH_PX (96)
    O texto e escrito horizontalmente; por padrao usa alinhamento à esquerda
    (o driver faz a rotacao interna ao converter para dots).
    """
    label_length_px = label_length_mm * DENSITY

    font = _load_font(font_size)

    # Canvas no formato esperado pelo driver: (comprimento x 96)
    img_w = label_length_px   # ex: 400
    img_h = LABEL_WIDTH_PX    # 96

    # Imagem temporaria para medir texto
    dummy = Image.new("L", (1, 1), 255)
    draw = ImageDraw.Draw(dummy)

    padding = 6
    text_area_w = img_w - 2 * padding
    text_area_h = img_h - 2 * padding

    # Quebra texto para caber na largura
    lines = _wrap_text(text, draw, font, text_area_w)

    # Calcula altura total do texto
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 4
    total_text_h = sum(line_heights) + max(0, len(lines) - 1) * line_spacing

    img = Image.new("L", (img_w, img_h), 255)
    draw = ImageDraw.Draw(img)

    # Centraliza verticalmente
    y_start = padding + max(0, (text_area_h - total_text_h) // 2)

    y = y_start
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        # Alinhamento horizontal: left / center / right
        if align == "left":
            x = padding
        elif align == "right":
            x = padding + max(0, text_area_w - line_w)
        else:  # center
            x = padding + max(0, (text_area_w - line_w) // 2)

        draw.text((x, y), line, font=font, fill=0)
        y += line_heights[i] + line_spacing

    return img


def _wrap_text(text, draw, font, max_width):
    """Quebra texto em linhas que cabem na largura."""
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines or [""]


async def print_via_ble(
    image: Image.Image,
    address: str = "DD:FE:25:83:BE:69",
    label_length_mm: int = 50,
) -> bool:
    """Imprime imagem via BLE usando o driver phomemo-q30-driver."""
    try:
        from phomemo_q30 import PhomemoQ30
    except ImportError:
        print("ERRO: phomemo-q30-driver nao encontrado no path!")
        print(f"  Verificar: {DRIVER_DIR}")
        return False
    
    # Salva imagem temporariamente
    tmp_path = "/tmp/phomemo_label.png"
    image.save(tmp_path)
    print(f"Imagem gerada: {image.size[0]}x{image.size[1]}px -> {tmp_path}")
    
    printer = PhomemoQ30(label_length_mm)
    
    def on_status(status_type, value):
        print(f"  Status: {status_type} = {value}")
    
    printer.set_status_callback(on_status)
    
    print(f"Conectando via BLE a {address}...")
    if not await printer.connect_async(address):
        print("ERRO: Nao conseguiu conectar via BLE!")
        print("  Verifique se a impressora esta ligada e proxima.")
        return False
    
    print("Conectado! Obtendo info...")
    await printer.get_printer_info_async()
    
    info = printer.printer_info
    print(f"  Bateria: {info.get('battery', '?')}%")
    print(f"  Papel: {'OK' if info.get('paper') else 'Sem papel' if info.get('paper') is False else '?'}")
    
    print(f"Imprimindo etiqueta ({label_length_mm}mm)...")
    success = await printer.print_image_async(tmp_path)
    
    if success:
        print("Impressao enviada com sucesso!")
    else:
        print("ERRO: Falha ao enviar impressao!")
    
    await printer.disconnect_async()
    print("Desconectado.")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Imprime texto em etiquetas Phomemo Q30 via BLE")
    parser.add_argument("--text", required=True, help="Texto a imprimir")
    parser.add_argument("--address", default="DD:FE:25:83:BE:69",
                        help="MAC BLE da impressora")
    parser.add_argument("--length", type=int, default=50,
                        choices=SUPPORTED_LENGTHS,
                        help="Comprimento da etiqueta em mm (padrao: 50)")
    parser.add_argument("--font-size", type=int, default=28,
                        help="Tamanho da fonte")
    parser.add_argument("--copies", type=int, default=1,
                        help="Numero de copias")
    parser.add_argument("--preview", type=str,
                        help="Salva preview da imagem (nao imprime)")
    args = parser.parse_args()
    
    # Gera imagem
    image = create_label_image(
        args.text,
        label_length_mm=args.length,
        font_size=args.font_size,
    )
    
    if args.preview:
        image.save(args.preview)
        print(f"Preview salva em: {args.preview}")
        return 0
    
    # Imprime via BLE
    for copy_num in range(1, args.copies + 1):
        if args.copies > 1:
            print(f"\n--- Copia {copy_num}/{args.copies} ---")
        
        success = asyncio.run(print_via_ble(
            image,
            address=args.address,
            label_length_mm=args.length,
        ))
        
        if not success:
            print(f"Falha na copia {copy_num}!")
            return 1
        
        if copy_num < args.copies:
            import time
            time.sleep(2)  # Intervalo entre copias
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
