from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path("/home/edenilson/eddie-auto-dev/tools/homelab/ltfs_cache_flush.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("ltfs_cache_flush", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_choose_target_uses_most_free():
    module = _load_module()
    candidate = module.FileCandidate(
        source_root=Path("/buffer"),
        source_path=Path("/buffer/demo.txt"),
        relative_path=Path("demo.txt"),
        size=10,
        mtime_ns=1,
        stable_since=1.0,
    )
    targets = [
        module.TargetRoot(Path("/tape-a"), "tape-a", total_bytes=100, free_bytes=40),
        module.TargetRoot(Path("/tape-b"), "tape-b", total_bytes=100, free_bytes=60),
    ]

    chosen = module.choose_target(candidate, targets, "most-free")

    assert chosen.name == "tape-b"


def test_flush_candidate_overwrites_existing_destination(tmp_path):
    module = _load_module()
    buffer_root = tmp_path / "buffer"
    target_root = tmp_path / "tape-a"
    source_path = buffer_root / "docs" / "report.txt"
    destination_path = target_root / "docs" / "report.txt"
    source_path.parent.mkdir(parents=True)
    destination_path.parent.mkdir(parents=True)
    destination_path.write_text("old\n", encoding="utf-8")
    source_path.write_text("newer\n", encoding="utf-8")

    candidate = module.FileCandidate(
        source_root=buffer_root,
        source_path=source_path,
        relative_path=Path("docs/report.txt"),
        size=source_path.stat().st_size,
        mtime_ns=source_path.stat().st_mtime_ns,
        stable_since=1.0,
    )
    target = module.TargetRoot(
        root=target_root,
        name="tape-a",
        total_bytes=10_000,
        free_bytes=10_000,
    )

    ok = module.flush_candidate(candidate, target)

    assert ok is True
    assert source_path.exists() is False
    assert destination_path.read_text(encoding="utf-8") == "newer\n"
