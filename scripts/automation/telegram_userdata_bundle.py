#!/usr/bin/env python3
"""Empacota e restaura userdata do Chrome para automação Telegram via Selenium."""

from __future__ import annotations

import argparse
import shutil
import tarfile
from pathlib import Path


def _safe_resolve(path: Path) -> Path:
    """Resolve caminho expandindo '~' e normalizando para absoluto."""
    return path.expanduser().resolve()


def _ensure_within(base: Path, target: Path) -> None:
    """Impede escrita fora do diretório base durante extração."""
    base_resolved = _safe_resolve(base)
    target_resolved = _safe_resolve(target)
    if not str(target_resolved).startswith(str(base_resolved) + "/") and target_resolved != base_resolved:
        raise ValueError(f"caminho inseguro detectado na extração: {target}")


def pack_profile(profile_dir: Path, archive_file: Path) -> Path:
    """Empacota o diretório de profile em tar.gz e retorna o caminho gerado."""
    source = _safe_resolve(profile_dir)
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"profile-dir inexistente: {source}")

    archive = archive_file.expanduser().resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "w:gz") as tf:
        tf.add(source, arcname=source.name)

    archive.chmod(0o600)
    return archive


def unpack_profile(archive_file: Path, dest_parent: Path, *, clean: bool = False) -> Path:
    """Restaura um profile empacotado e retorna diretório restaurado."""
    archive = _safe_resolve(archive_file)
    if not archive.exists() or not archive.is_file():
        raise FileNotFoundError(f"arquivo de bundle inexistente: {archive}")

    parent = _safe_resolve(dest_parent)
    parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        roots = {m.name.split("/")[0] for m in members if m.name and m.name.strip()}
        if len(roots) != 1:
            raise ValueError("bundle inválido: esperado exatamente um diretório raiz")
        root_name = next(iter(roots))
        restored = parent / root_name
        if clean and restored.exists():
            shutil.rmtree(restored)

        for member in members:
            member_path = parent / member.name
            _ensure_within(parent, member_path)
        tf.extractall(parent)

    return restored


def _build_parser() -> argparse.ArgumentParser:
    """Cria parser de linha de comando para pack/unpack."""
    parser = argparse.ArgumentParser(
        description="Gerencia bundle de userdata do Chrome para automação Telegram."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pack = sub.add_parser("pack", help="Empacota profile em .tar.gz")
    pack.add_argument("--profile-dir", required=True, help="Diretório de userdata do Chrome")
    pack.add_argument("--archive-file", required=True, help="Arquivo de saída .tar.gz")

    unpack = sub.add_parser("unpack", help="Restaura bundle de profile")
    unpack.add_argument("--archive-file", required=True, help="Arquivo .tar.gz de entrada")
    unpack.add_argument("--dest-parent", required=True, help="Diretório pai para restaurar profile")
    unpack.add_argument(
        "--clean",
        action="store_true",
        help="Remove profile restaurado previamente antes de extrair",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entrada principal de CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "pack":
        out = pack_profile(Path(args.profile_dir), Path(args.archive_file))
        print(f"bundle_gerado={out}")
        return 0

    out = unpack_profile(Path(args.archive_file), Path(args.dest_parent), clean=bool(args.clean))
    print(f"profile_restaurado={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
