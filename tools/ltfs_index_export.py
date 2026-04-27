#!/usr/bin/env python3
"""
ltfs_index_export.py — Exporta automaticamente o índice LTFS após cada sessão de escrita.

Uso:
  ltfs_index_export.py [--device /dev/sgX] [--dest /mnt/raid1/ltfs-indexes]

Lê Partition 0 (Index Partition) da fita LTFS inserida no drive,
extrai o XML do índice e salva com nome: <VOLSER>_<YYYYMMDD_HHMMSS>.xml

Deve ser executado:
- Após cada `ltfs umount`
- Via cron (ex: post-unmount hook)
- Manualmente quando necessário
"""

import argparse
import os
import sys
import subprocess
import re
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ltfs-index-export")


def get_nst_device(sg_device: str) -> str:
    """Converte /dev/sgX para /dev/nstY baseado no host SCSI.

    Retorna sempre o dispositivo base (ex: nst0, não nst0l/nst0a/nst0m).
    """
    sg_num = sg_device.replace("/dev/sg", "")
    # Preferência: nstN exato (sem sufixo de densidade)
    sg_sys = Path(f"/sys/class/scsi_generic/sg{sg_num}/device")
    if sg_sys.exists():
        tape_dir = sg_sys / "scsi_tape"
        if tape_dir.exists():
            exact = f"nst{sg_num}"
            if (tape_dir / exact).exists():
                return f"/dev/{exact}"
            # Fallback: primeiro nstN* sem sufixo de densidade
            for child in sorted(tape_dir.iterdir()):
                name = child.name
                if name == f"nst{sg_num}" or (name.startswith(f"nst{sg_num}") and len(name) == len(f"nst{sg_num}")):
                    return f"/dev/{name}"
    # Último recurso
    mapping = {"0": "nst0", "1": "nst1", "2": "nst2"}
    return f"/dev/{mapping.get(sg_num, f'nst{sg_num}')}"


def read_volser(nst_device: str) -> str:
    """Lê o VOL1 label no bloco 0 para extrair o VOLSER."""
    subprocess.run(["mt", "-f", nst_device, "rewind"], check=True, timeout=60)
    fd = os.open(nst_device, os.O_RDONLY)
    try:
        data = os.read(fd, 80)
        if data[:4] == b"VOL1":
            volser = data[4:10].decode("ascii", errors="replace").strip()
            return volser
        logger.warning("Bloco 0 não é VOL1 label: %s", data[:10])
        return "UNKNOWN"
    finally:
        os.close(fd)


def extract_index_from_partition0(nst_device: str, dest_dir: Path, volser: str) -> Path:
    """Lê sequencialmente Partition 0 e extrai o XML ltfsindex."""
    logger.info("Rebobinando %s...", nst_device)
    subprocess.run(["mt", "-f", nst_device, "rewind"], check=True, timeout=60)

    logger.info("Lendo Partition 0 sequencialmente...")
    fd = os.open(nst_device, os.O_RDONLY)
    raw_data = bytearray()
    blk = 0
    max_blocks = 500  # Safety limit

    try:
        while blk < max_blocks:
            try:
                data = os.read(fd, 524288)
                if not data:
                    blk += 1
                    continue
                raw_data.extend(data)
                blk += 1
            except OSError:
                break
    finally:
        os.close(fd)

    logger.info("Lidos %d bytes de %d blocos", len(raw_data), blk)

    # Extrair XML ltfsindex
    idx_start = raw_data.find(b"<ltfsindex")
    if idx_start < 0:
        raise RuntimeError("ltfsindex não encontrado na Partition 0")

    idx_end = raw_data.rfind(b"</ltfsindex>")
    if idx_end < 0:
        raise RuntimeError("Tag de fechamento </ltfsindex> não encontrada")

    xml_data = bytes(raw_data[idx_start:idx_end + len(b"</ltfsindex>") + 1])
    logger.info("Índice XML extraído: %d bytes", len(xml_data))

    # Salvar com timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dest_dir / f"{volser}_{ts}.xml"
    filename.write_bytes(xml_data)
    logger.info("Salvo em: %s", filename)

    # Criar symlink 'latest'
    latest = dest_dir / f"{volser}_latest.xml"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(filename.name)

    # Estatísticas rápidas
    file_count = xml_data.count(b"<file>")
    dir_count = xml_data.count(b"<directory>")
    logger.info("Conteúdo: %d arquivos, %d diretórios", file_count, dir_count)

    return filename


def feed_ltfs_catalog(xml_path: Path) -> None:
    """Alimenta o ltfs-catalog (se disponível) com o index exportado."""
    catalog_cmd = Path("/usr/local/sbin/ltfs-catalog")
    if catalog_cmd.exists():
        logger.info("Alimentando ltfs-catalog com %s...", xml_path.name)
        try:
            result = subprocess.run(
                [str(catalog_cmd), "--index", str(xml_path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                logger.info("ltfs-catalog atualizado com sucesso")
            else:
                logger.warning("ltfs-catalog retornou %d: %s", result.returncode, result.stderr[:200])
        except Exception as e:
            logger.warning("Falha ao alimentar ltfs-catalog: %s", e)
    else:
        logger.info("ltfs-catalog não encontrado, pulando...")


def main() -> None:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(description="Exporta índice LTFS da fita para armazenamento permanente")
    parser.add_argument("--device", default="/dev/sg1", help="Device sg do drive (default: /dev/sg1)")
    parser.add_argument("--dest", default="/mnt/raid1/ltfs-indexes", help="Diretório destino")
    parser.add_argument("--feed-catalog", action="store_true", help="Alimentar ltfs-catalog após export")
    args = parser.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    nst = get_nst_device(args.device)
    logger.info("Usando device: %s (nst: %s)", args.device, nst)

    # Guard: verificar se drive está acessível antes de tentar I/O
    probe = subprocess.run(
        ["mt", "-f", nst, "status"],
        capture_output=True, timeout=15
    )
    if probe.returncode != 0:
        logger.warning(
            "Drive %s não acessível após unmount (rc=%d): %s — pulando export.",
            nst, probe.returncode, (probe.stderr or probe.stdout).decode(errors="replace").strip()[:200],
        )
        sys.exit(0)

    volser = read_volser(nst)
    logger.info("VOLSER: %s", volser)

    xml_path = extract_index_from_partition0(nst, dest, volser)

    if args.feed_catalog:
        feed_ltfs_catalog(xml_path)

    logger.info("Export concluído: %s", xml_path)


if __name__ == "__main__":
    main()
