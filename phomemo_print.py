"""Helper to send print jobs to a Phomemo Q30 over its Bluetooth serial port."""
import argparse
import logging
from pathlib import Path
from typing import Iterable, Optional

import serial
from serial.tools import list_ports

try:
    from PIL import Image
    from PIL import ImageOps
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

DEFAULT_BAUDRATE = 9600
DEFAULT_PORT_HINT = "PHOMEMO"
FORM_FEED = b"\x0c"


class PrinterError(Exception):
    pass


def discover_ports(hint: Optional[str] = None) -> Iterable[list_ports.ListPortInfo]:
    """List available serial ports and optionally filter by the provided hint."""
    ports = list(list_ports.comports())
    if hint:
        hint_lower = hint.lower()
        return [p for p in ports if hint_lower in (p.description or "").lower() or hint_lower in (p.manufacturer or "").lower()]
    return ports


def choose_port(port_name: Optional[str], hint: str) -> str:
    """Return a concrete serial port to use, preferring the hint if the user omitted --port."""
    if port_name:
        return port_name

    matches = list(discover_ports(hint))
    if not matches:
        raise PrinterError("Nenhuma porta serial compatível com o Phomemo foi encontrada. Verifique emparelhamento Bluetooth e reinicie o script.")

    if len(matches) > 1:
        logger.info("Portas encontradas, usando a primeira: %s", matches[0].device)
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


def print_image(printer: serial.Serial, image_path: Path) -> None:
    """Envia uma imagem monocromática para o Phomemo usando comando raster."""
    if Image is None:
        raise PrinterError("Pillow não instalado. Rode: pip install pillow")

    image = Image.open(image_path)
    max_width = 384
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


def print_text(printer: serial.Serial, text: str) -> None:
    """Envio simples de texto, respeitando inicialização ESC/POS."""
    printer.write(b"\x1b@")
    printer.write(text.replace("\r", "").encode("utf-8", "replace"))
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

    logger.info("Conectando-se à porta %s (baud=%d)", port, args.baud)

    with open_printer(port, args.baud) as printer:
        if args.image:
            logger.info("Imprimindo imagem %s", args.image)
            print_image(printer, args.image)
        else:
            logger.info("Imprimindo texto simples")
            print_text(printer, args.text)

    logger.info("Trabalho enviado!")


if __name__ == "__main__":
    main()
