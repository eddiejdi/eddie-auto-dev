from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path("scripts/automation/gdrive_to_nextcloud_pilot.py").resolve()
SPEC = importlib.util.spec_from_file_location("gdrive_to_nextcloud_pilot", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Falha ao carregar módulo de migração piloto")

pilot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pilot
SPEC.loader.exec_module(pilot)


def test_build_webdav_path_encodes_segments() -> None:
    result = pilot.build_webdav_path(
        remote_dir="RPA4ALL/Migracoes Piloto",
        relative_path="Pasta A/arquivo 1.txt",
    )

    assert result == "RPA4ALL/Migracoes%20Piloto/Pasta%20A/arquivo%201.txt"


def test_list_local_files_returns_sorted_files(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a" / "a.txt").write_text("a", encoding="utf-8")

    files = pilot.list_local_files(tmp_path)

    assert [item.relative_to(tmp_path).as_posix() for item in files] == ["a/a.txt", "b/z.txt"]


def test_to_file_entries_and_baseline(tmp_path: Path) -> None:
    file_path = tmp_path / "curriculos" / "joao.txt"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("conteudo piloto", encoding="utf-8")

    files = pilot.list_local_files(tmp_path)
    entries = pilot.to_file_entries(source_dir=tmp_path, files=files)
    baseline = pilot.build_baseline(source_dir=tmp_path, remote_dir="RPA4ALL/Piloto", entries=entries)

    assert len(entries) == 1
    assert entries[0].relative_path == "curriculos/joao.txt"
    assert entries[0].size_bytes > 0
    assert len(entries[0].sha256) == 64
    assert baseline["total_files"] == 1
    assert baseline["total_bytes"] == entries[0].size_bytes
    assert baseline["entries"][0]["relative_path"] == "curriculos/joao.txt"


def test_migrate_files_dry_run_marks_all_as_skipped(tmp_path: Path) -> None:
    file_path = tmp_path / "arquivo.txt"
    file_path.write_text("conteudo", encoding="utf-8")
    files = pilot.list_local_files(tmp_path)
    entries = pilot.to_file_entries(source_dir=tmp_path, files=files)

    report = asyncio.run(
        pilot.migrate_files(
            source_dir=tmp_path,
            remote_dir="RPA4ALL/Piloto",
            entries=entries,
            client=None,
            dry_run=True,
            max_concurrency=2,
            skip_existing=False,
        )
    )

    assert report.total_files == 1
    assert report.skipped_files == 1
    assert report.uploaded_files == 0
    assert report.failed_files == 0