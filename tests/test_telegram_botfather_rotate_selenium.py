#!/usr/bin/env python3
"""Testes unitários para o RPA de rotação de token do BotFather."""

from __future__ import annotations

import importlib.util
import sys
import tarfile
from pathlib import Path


_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "automation"
    / "telegram_botfather_rotate_selenium.py"
)
_SPEC = importlib.util.spec_from_file_location("telegram_botfather_rotate_selenium", str(_SCRIPT_PATH))
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["telegram_botfather_rotate_selenium"] = _MODULE
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)


def test_extract_latest_token_returns_last_match() -> None:
    """Deve retornar o último token encontrado em uma conversa."""
    text = (
        "Old token: 123456:ABCDEFGHIJKLMNOPQRSTUVWX-1234\n"
        "New token: 654321:ZYXWVUTSRQPONMLKJIHGFEDCBA_9876"
    )
    token = _MODULE.extract_latest_token(text)
    assert token == "654321:ZYXWVUTSRQPONMLKJIHGFEDCBA_9876"


def test_extract_latest_token_returns_none_when_not_found() -> None:
    """Sem padrão de token válido, o retorno deve ser None."""
    assert _MODULE.extract_latest_token("sem token aqui") is None


def test_mask_secret_masks_middle_of_value() -> None:
    """A máscara deve preservar apenas começo e fim do segredo."""
    masked = _MODULE.mask_secret("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ_12345")
    assert masked.startswith("123456")
    assert masked.endswith("2345")
    assert "..." in masked


def test_write_secret_file_creates_restricted_permissions(tmp_path: Path) -> None:
    """Arquivo do token deve ser escrito com permissão 0600."""
    out = tmp_path / "token.txt"
    saved = _MODULE.write_secret_file("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ_12345", out)
    assert saved == out
    assert out.read_text(encoding="utf-8") == "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ_12345"
    assert (out.stat().st_mode & 0o777) == 0o600


def test_render_post_rotate_command_replaces_placeholder(tmp_path: Path) -> None:
    """Template de comando deve receber o caminho do arquivo token."""
    token_file = tmp_path / "tk.txt"
    rendered = _MODULE.render_post_rotate_command("cmd --token-file {token_file}", token_file)
    assert rendered == f"cmd --token-file {token_file}"


def test_parse_args_defaults() -> None:
    """Parser deve normalizar username e aplicar defaults esperados."""
    cfg = _MODULE.parse_args(["--bot-username", "@MeuBot"])
    assert cfg.bot_username == "MeuBot"
    assert cfg.timeout_seconds >= 30
    assert cfg.chrome_binary is None
    assert cfg.chromedriver_path is None
    assert cfg.profile_archive is None
    assert cfg.post_rotate_cmd is None


def test_parse_args_accepts_profile_archive() -> None:
    """Parser deve aceitar bundle de profile e flag de limpeza."""
    cfg = _MODULE.parse_args(
        [
            "--bot-username",
            "botx",
            "--profile-archive",
            "/tmp/profile.tgz",
            "--profile-archive-clean",
        ]
    )
    assert str(cfg.profile_archive) == "/tmp/profile.tgz"
    assert cfg.profile_archive_clean is True


def test_parse_args_accepts_chrome_binary() -> None:
    """Parser deve aceitar caminho explícito do Chrome."""
    cfg = _MODULE.parse_args(["--bot-username", "botx", "--chrome-binary", "/opt/google/chrome/chrome"])
    assert str(cfg.chrome_binary) == "/opt/google/chrome/chrome"


def test_parse_args_accepts_chromedriver_path() -> None:
    """Parser deve aceitar caminho explícito do chromedriver."""
    cfg = _MODULE.parse_args(["--bot-username", "botx", "--chromedriver-path", "/home/homelab/.local/bin/chromedriver"])
    assert str(cfg.chromedriver_path) == "/home/homelab/.local/bin/chromedriver"


def test_restore_profile_archive_restores_expected_dir(tmp_path: Path) -> None:
    """Bundle válido deve ser restaurado para profile-dir solicitado."""
    src_parent = tmp_path / "src"
    src_profile = src_parent / "telegram-profile"
    src_profile.mkdir(parents=True)
    (src_profile / "marker.txt").write_text("ok", encoding="utf-8")

    archive = tmp_path / "bundle.tgz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src_profile, arcname=src_profile.name)

    target_profile = tmp_path / "target" / "telegram-profile"
    restored = _MODULE.restore_profile_archive(archive, target_profile, clean=False)
    assert restored == target_profile
    assert (target_profile / "marker.txt").read_text(encoding="utf-8") == "ok"


def test_click_revoke_current_token_raises_without_driver() -> None:
    """_click_revoke_current_token deve estar acessível e levantar erro com driver inválido."""
    import pytest

    assert hasattr(_MODULE, "_click_revoke_current_token")
    with pytest.raises(Exception):
        _MODULE._click_revoke_current_token(None, 1)
