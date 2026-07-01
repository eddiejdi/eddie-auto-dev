#!/usr/bin/env python3
"""Testes unitários para bundle de userdata Telegram Selenium."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "automation"
    / "telegram_userdata_bundle.py"
)
_SPEC = importlib.util.spec_from_file_location("telegram_userdata_bundle", str(_SCRIPT_PATH))
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["telegram_userdata_bundle"] = _MODULE
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)


def test_pack_profile_generates_archive_with_permission_600(tmp_path: Path) -> None:
    """Pack deve gerar arquivo e limitar permissão de leitura."""
    profile = tmp_path / "telegram-profile"
    profile.mkdir()
    (profile / "state.txt").write_text("alive", encoding="utf-8")

    archive = tmp_path / "bundle.tgz"
    out = _MODULE.pack_profile(profile, archive)

    assert out == archive
    assert archive.exists()
    assert (archive.stat().st_mode & 0o777) == 0o600


def test_unpack_profile_restores_files(tmp_path: Path) -> None:
    """Unpack deve restaurar estrutura do profile."""
    profile = tmp_path / "p1"
    profile.mkdir()
    (profile / "prefs.json").write_text('{"ok":true}', encoding="utf-8")

    bundle = tmp_path / "bundle.tgz"
    _MODULE.pack_profile(profile, bundle)

    dest_parent = tmp_path / "restore"
    restored = _MODULE.unpack_profile(bundle, dest_parent, clean=False)
    assert restored == dest_parent / "p1"
    assert (restored / "prefs.json").read_text(encoding="utf-8") == '{"ok":true}'
