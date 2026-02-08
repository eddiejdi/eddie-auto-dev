"""Helper to send print jobs to a Phomemo Q30 over its Bluetooth serial port."""
import argparse
import json
import logging
from pathlib import Path
from typing import Iterable, Optional, Union

import serial
from serial.tools import list_ports

try:
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont
    from PIL import ImageOps
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

DEFAULT_BAUDRATE = 9600
DEFAULT_PORT_HINT = "PHOMEMO"
DEFAULT_MAX_WIDTH = 384
DEFAULT_DPI = 203
DEFAULT_FONT_SIZE = 28
FORM_FEED = b"\x0c"


class PrinterError(Exception):
    pass


def discover_ports(hint: Optional[str] = None):
    """List available serial ports and optionally filter by the provided hint.
    
    Supports both Bluetooth and USB connections:
    - Bluetooth: appears as "PHOMEMO" in description or manufacturer
    - USB: appears with VID:PID like "2e8d:000c" or similar manufacturer
    """
    ports = list(list_ports.comports())
    if hint:
        hint_lower = hint.lower()
        return [p for p in ports if hint_lower in (p.description or "").lower() 
                or hint_lower in (p.manufacturer or "").lower()
                or hint_lower in (p.hwid or "").lower()]
    return ports


def choose_port(port_name: Optional[str], hint: str) -> str:
    """Return a concrete serial port to use, preferring the hint if the user omitted --port."""
    if port_name:
        return port_name

    matches = list(discover_ports(hint))
    if not matches:
        rfcomm_ports = [p for p in list_ports.comports() if (p.device or "").startswith("/dev/rfcomm")]
        if rfcomm_ports:
            if len(rfcomm_ports) > 1:
                logger.info("Portas rfcomm encontradas, usando a primeira: %s", rfcomm_ports[0].device)
            return rfcomm_ports[0].device

        msg = (
            "Nenhuma porta serial compatível com o Phomemo foi encontrada.\n"
            "Se usar Bluetooth: verifique emparelhamento e reinicie.\n"
            "Se usar USB: conecte a impressora e verifique com 'ls /dev/ttyUSB*' ou 'lsusb'.\n"
            "Se usar Bluetooth manual: verifique /dev/rfcomm0 e tente --port /dev/rfcomm0.\n"
            "Para listar portas disponíveis, execute: python phomemo_print.py --list"
        )
        raise PrinterError(msg)

    if len(matches) > 1:
        logger.info("Portas encontradas, usando a primeira: %s (%s)", matches[0].device, matches[0].description)
    return matches[0].device


def _rasterize(image: "Image.Image") -> tuple[int, int, bytearray]:
    """Renderiza a imagem como bitmap compatível com ESC/POS (GS v 0)."""
    if image.mode != "1":
        image = ImageOps.grayscale(image).point(lambda px: 0 if px < 128 else 255, mode="1")

    width = image.width
    height = image.height
    row_bytes = (width + 7) // 8
    buffer = bytearray()

    for y in range(height):
        for byte_index in range(row_bytes):
            byte = 0
            for bit in range(8):
                x = byte_index * 8 + (7 - bit)
                if x >= width:
                    continue
                if image.getpixel((x, y)) == 0:
                    byte |= 1 << bit
            buffer.append(byte)
    return row_bytes, height, buffer


def _load_font(size: int) -> "ImageFont.ImageFont":
    """Carrega uma fonte TrueType (se disponivel) com fallback para a padrao."""
    if ImageFont is None:
        raise PrinterError("Pillow nao instalado. Rode: pip install pillow")

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def _measure_text(draw: "ImageDraw.ImageDraw", text: str, font: "ImageFont.ImageFont") -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_text(text: str, draw: "ImageDraw.ImageDraw", font: "ImageFont.ImageFont", max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue

        words = paragraph.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            width, _ = _measure_text(draw, candidate, font)
            if width <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word

        if line:
            lines.append(line)

    return lines or [""]


def _in_to_px(value_in: Optional[float], dpi: int) -> Optional[int]:
    if value_in is None:
        return None
    return max(1, int(round(value_in * dpi)))


def render_text_image(
    text: str,
    max_width: int = DEFAULT_MAX_WIDTH,
    label_height: Optional[int] = None,
    padding: int = 10,
    line_spacing: int = 6,
    font_size: int = DEFAULT_FONT_SIZE,
) -> "Image.Image":
    if Image is None or ImageDraw is None or ImageFont is None:
        raise PrinterError("Pillow nao instalado. Rode: pip install pillow")

    font = _load_font(font_size)
    dummy = Image.new("L", (1, 1), 255)
    dummy_draw = ImageDraw.Draw(dummy)
    if max_width <= padding * 2:
        max_width = padding * 2 + 10

    max_text_width = max_width - 2 * padding
    lines = _wrap_text(text, dummy_draw, font, max_text_width)
    _, line_height = _measure_text(dummy_draw, "Ag", font)
    height = padding * 2 + len(lines) * line_height + max(0, len(lines) - 1) * line_spacing
    if label_height is not None:
        height = max(height, label_height)

    image = Image.new("L", (max_width, height), 255)
    draw = ImageDraw.Draw(image)

    y = padding
    for line in lines:
        line_width, _ = _measure_text(draw, line, font)
        x = padding + max(0, (max_text_width - line_width) // 2)
        draw.text((x, y), line, font=font, fill=0)
        y += line_height + line_spacing

    return image


def print_image(printer: serial.Serial, image_input: Union[Path, "Image.Image"]) -> None:
    """Envia uma imagem monocromatica para o Phomemo usando comando raster."""
    if Image is None:
        raise PrinterError("Pillow não instalado. Rode: pip install pillow")

    if isinstance(image_input, Path):
        image = Image.open(image_input)
    else:
        image = image_input

    max_width = DEFAULT_MAX_WIDTH
    if image.width > max_width:
        ratio = max_width / image.width
        size = (max_width, int(image.height * ratio))
        image = image.resize(size, Image.LANCZOS)

    row_bytes, height, bitmap = _rasterize(image)

    header = bytearray(b"\x1d\x76\x30\x00")
    header.append(row_bytes % 256)
    header.append(row_bytes // 256)
    header.append(height % 256)
    header.append(height // 256)

    printer.write(header + bitmap)
    printer.write(FORM_FEED)
    printer.flush()


def print_text(
    printer: serial.Serial,
    text: str,
    use_image: bool = True,
    max_width: int = DEFAULT_MAX_WIDTH,
    label_height: Optional[int] = None,
    font_size: int = DEFAULT_FONT_SIZE,
) -> None:
    """Imprime texto via imagem (padrao) ou ESC/POS bruto."""
    if use_image:
        image = render_text_image(text, max_width=max_width, label_height=label_height, font_size=font_size)
        print_image(printer, image)
        return
    import time
    
    # Inicializa a impressora
    printer.write(b"\x1b@")
    time.sleep(0.1)
    
    # Define alinhamento centralizado
    printer.write(b"\x1b\x61\x01")
    time.sleep(0.05)
    
    # Define texto em negrito
    printer.write(b"\x1b\x45\x01")
    time.sleep(0.05)
    
    # Define tamanho de fonte grande
    printer.write(b"\x1d\x21\x11")
    time.sleep(0.05)
    
    # Seleciona codepage (UTF-8 / Latin-1)
    printer.write(b"\x1b\x74\x00")
    time.sleep(0.05)
    
    # Envia o texto
    printer.write(text.replace("\r", "").encode("cp437", "replace"))
    printer.write(b"\n\n\n")
    time.sleep(0.1)
    
    # Desliga negrito e retorna ao tamanho normal
    printer.write(b"\x1b\x45\x00")
    printer.write(b"\x1d\x21\x00")
    printer.write(b"\x1b\x61\x00")  # Alinhamento esquerda
    time.sleep(0.1)
    
    # Envia o texto linha por linha
    for line in text.split('\n'):
        if line.strip():
            printer.write(line.encode("cp437", "replace"))
            printer.write(b"\n")
    
    printer.write(b"\n\n")
    
    # Reset de formatação
    printer.write(b"\x1b\x45\x00")  # ESC E 0 - bold off
    printer.write(b"\x1d\x21\x00")  # GS ! 0 - normal size
    printer.write(b"\x1b\x61\x00")  # ESC a 0 - left align
    
    # Alimenta papel
    printer.write(b"\n\n")
    printer.write(FORM_FEED)
    printer.flush()


def open_printer(port: str, baudrate: int) -> serial.Serial:
    return serial.Serial(port=port, baudrate=baudrate, timeout=1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Imprime texto ou imagens em um Phomemo Q30 emparelhado via Bluetooth.")
    parser.add_argument("--list", action="store_true", help="Lista portas seriais disponíveis e sai.")
    parser.add_argument("--port", help="Porta serial dedicada (ex: COM6)." )
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Velocidade de comunicação (padrão: 9600).")
    parser.add_argument("--hint", default=DEFAULT_PORT_HINT, help="Substring usada para identificar a porta do Phomemo.")
    parser.add_argument("--text", default="Eddie says hello!", help="Texto a ser impresso (UTF-8).")
    parser.add_argument("--image", type=Path, help="Caminho para PNG/BMP sendo enviado ao printer.")
    parser.add_argument(
        "--text-mode",
        choices=["image", "escpos"],
        default="image",
        help="Modo de impressao do texto (image ou escpos).",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=DEFAULT_FONT_SIZE,
        help="Tamanho da fonte quando usar text-mode=image.",
    )
    parser.add_argument(
        "--label-width-in",
        type=float,
        help="Largura da etiqueta em polegadas (ex: 0.6).",
    )
    parser.add_argument(
        "--label-height-in",
        type=float,
        help="Altura da etiqueta em polegadas (ex: 2.0).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="DPI usado para converter polegadas em pixels (padrao: 203).",
    )
    parser.add_argument("--status", action="store_true", help="Consulta status/conectividade da impressora e sai.")
    args = parser.parse_args()

    if args.list:
        ports = list(discover_ports())
        if not ports:
            logger.info("Nenhuma porta serial encontrada.")
            return
        for port in ports:
            logger.info("%s - %s", port.device, port.description)
        return

    try:
        port = choose_port(args.port, args.hint)
    except PrinterError as exc:
        logger.error(exc)
        raise SystemExit(1) from exc

    # Se apenas consultar status, abre a porta e devolve um resumo simples
    logger.info("Conectando-se à porta %s (baud=%d)", port, args.baud)

    if args.status:
        try:
            status = {
                "port": port,
                "baud": args.baud,
                "open_ok": False,
                "init_ok": False,
                "read_bytes": None,
                "message": "",
            }
            try:
                with open_printer(port, args.baud) as printer:
                    status["open_ok"] = True
                    try:
                        printer.write(b"\x1b@")
                        printer.flush()
                        status["init_ok"] = True
                    except Exception as e:
                        status["message"] += f"init_error: {e}; "

                    try:
                        # Leia qualquer byte disponível
                        if hasattr(printer, "in_waiting") and printer.in_waiting:
                            data = printer.read(printer.in_waiting)
                            status["read_bytes"] = data.hex()
                        else:
                            status["read_bytes"] = None
                    except Exception as e:
                        status["message"] += f"read_error: {e}; "

            except Exception as e:
                status["message"] += f"open_error: {e}; "

            # Saída JSON amigável para consumo por outros serviços
            print(json.dumps(status))
            return
        except Exception as exc:
            logger.error("Erro ao consultar status da impressora: %s", exc)
            raise SystemExit(1) from exc

    with open_printer(port, args.baud) as printer:
        if args.image:
            logger.info("Imprimindo imagem %s", args.image)
            print_image(printer, args.image)
        else:
            logger.info("Imprimindo texto (%s)", args.text_mode)
            if args.text_mode == "image":
                width_px = _in_to_px(args.label_width_in, args.dpi) or DEFAULT_MAX_WIDTH
                height_px = _in_to_px(args.label_height_in, args.dpi)
                image = render_text_image(
                    args.text,
                    max_width=width_px,
                    label_height=height_px,
                    font_size=args.font_size,
                )
                print_image(printer, image)
            else:
                print_text(printer, args.text, use_image=False)

    logger.info("Trabalho enviado!")


if __name__ == "__main__":
    main()
