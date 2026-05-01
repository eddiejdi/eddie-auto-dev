"""
tests/test_safe_migrate.py — Testes unitários para tools/safe_migrate.py

Cobertura alvo: ≥80% do módulo safe_migrate.
Todos os I/Os externos (subprocess, filesystem) são mockados.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Garante que 'tools/' está no sys.path para import direto
sys.path.insert(0, str(Path(__file__).parent.parent))

import tools.safe_migrate as sm


# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────

@pytest.fixture()
def mock_logger() -> MagicMock:
    """Logger fake que não emite para nenhum handler real."""
    lg = MagicMock()
    lg.info = MagicMock()
    lg.debug = MagicMock()
    lg.warning = MagicMock()
    lg.error = MagicMock()
    return lg


@pytest.fixture()
def src_dir(tmp_path: Path) -> Path:
    """Diretório de origem com 3 arquivos de 10 bytes cada."""
    d = tmp_path / "Google_Drive_Pessoal"
    d.mkdir()
    for i in range(3):
        (d / f"file{i}.txt").write_bytes(b"0123456789")  # 10 bytes
    return d


@pytest.fixture()
def dst_local(tmp_path: Path) -> Path:
    """Diretório destino local simulando mount remoto."""
    d = tmp_path / "lts_mount" / "Google_Drive_Pessoal"
    d.mkdir(parents=True)
    return d


# ──────────────────────────────────────────────────────────
# Utilitários locais: _count_files_local, _bytes_total_local
# ──────────────────────────────────────────────────────────

class TestLocalCounts:
    def test_count_files_local_correct(self, src_dir: Path) -> None:
        assert sm._count_files_local(src_dir) == 3

    def test_bytes_total_local_correct(self, src_dir: Path) -> None:
        assert sm._bytes_total_local(src_dir) == 30  # 3 * 10 bytes


# ──────────────────────────────────────────────────────────
# _count_and_bytes_remote
# ──────────────────────────────────────────────────────────

class TestCountAndBytesRemote:
    def test_parses_remote_output_correctly(self, mock_logger: MagicMock) -> None:
        fake_result = MagicMock(returncode=0, stdout="42 1024\n", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            count, total = sm._count_and_bytes_remote(
                "homelab@192.168.15.2:/mnt/lts/folder",
                ssh_key=None,
                logger=mock_logger,
            )
        assert count == 42
        assert total == 1024
        mock_run.assert_called_once()

    def test_uses_ssh_key_when_present(self, mock_logger: MagicMock, tmp_path: Path) -> None:
        key = tmp_path / "id_rsa"
        key.touch()
        fake_result = MagicMock(returncode=0, stdout="1 100\n", stderr="")
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            sm._count_and_bytes_remote(
                "homelab@192.168.15.2:/mnt/lts/folder",
                ssh_key=key,
                logger=mock_logger,
            )
        cmd = mock_run.call_args[0][0]
        assert "-i" in cmd
        assert str(key) in cmd

    def test_raises_on_nonzero_ssh_exit(self, mock_logger: MagicMock) -> None:
        fake_result = MagicMock(returncode=1, stdout="", stderr="Permission denied")
        with patch("subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="SSH falhou"):
                sm._count_and_bytes_remote(
                    "homelab@192.168.15.2:/mnt/lts/folder",
                    ssh_key=None,
                    logger=mock_logger,
                )

    def test_raises_on_bad_dst_format(self, mock_logger: MagicMock) -> None:
        with pytest.raises(ValueError, match="user@host"):
            sm._count_and_bytes_remote("/bad/local/path", ssh_key=None, logger=mock_logger)

    def test_raises_on_unexpected_output(self, mock_logger: MagicMock) -> None:
        fake_result = MagicMock(returncode=0, stdout="unexpected\n", stderr="")
        with patch("subprocess.run", return_value=fake_result):
            with pytest.raises(RuntimeError, match="Saída inesperada"):
                sm._count_and_bytes_remote(
                    "homelab@192.168.15.2:/mnt/lts/folder",
                    ssh_key=None,
                    logger=mock_logger,
                )


# ──────────────────────────────────────────────────────────
# validate_transfer
# ──────────────────────────────────────────────────────────

class TestValidateTransfer:
    DST = "homelab@192.168.15.2:/mnt/lts/folder"

    def test_passes_when_count_and_bytes_match(
        self, src_dir: Path, mock_logger: MagicMock
    ) -> None:
        with patch.object(sm, "_count_and_bytes_remote", return_value=(3, 30)):
            result = sm.validate_transfer(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert result is True

    def test_fails_when_count_differs(self, src_dir: Path, mock_logger: MagicMock) -> None:
        with patch.object(sm, "_count_and_bytes_remote", return_value=(2, 30)):
            result = sm.validate_transfer(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert result is False
        mock_logger.error.assert_called()

    def test_fails_when_bytes_differ(self, src_dir: Path, mock_logger: MagicMock) -> None:
        with patch.object(sm, "_count_and_bytes_remote", return_value=(3, 25)):
            result = sm.validate_transfer(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert result is False

    def test_fails_when_remote_raises(self, src_dir: Path, mock_logger: MagicMock) -> None:
        with patch.object(sm, "_count_and_bytes_remote", side_effect=RuntimeError("SSH error")):
            result = sm.validate_transfer(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert result is False
        mock_logger.error.assert_called()


# ──────────────────────────────────────────────────────────
# run_rsync
# ──────────────────────────────────────────────────────────

class TestRunRsync:
    DST = "homelab@192.168.15.2:/mnt/lts/folder"

    def test_returns_zero_on_success(
        self, src_dir: Path, mock_logger: MagicMock
    ) -> None:
        fake_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            rc = sm.run_rsync(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert rc == 0
        mock_run.assert_called_once()

    def test_returns_nonzero_on_failure(
        self, src_dir: Path, mock_logger: MagicMock
    ) -> None:
        fake_result = MagicMock(returncode=23)
        with patch("subprocess.run", return_value=fake_result):
            rc = sm.run_rsync(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        assert rc == 23

    def test_includes_partial_and_append_verify(
        self, src_dir: Path, mock_logger: MagicMock
    ) -> None:
        fake_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            sm.run_rsync(src_dir, self.DST, ssh_key=None, logger=mock_logger)
        cmd = mock_run.call_args[0][0]
        assert "--partial" in cmd
        assert "--append-verify" in cmd

    def test_appends_ssh_key_to_e_option(
        self, src_dir: Path, mock_logger: MagicMock, tmp_path: Path
    ) -> None:
        key = tmp_path / "homelab_key"
        key.touch()
        fake_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=fake_result) as mock_run:
            sm.run_rsync(src_dir, self.DST, ssh_key=key, logger=mock_logger)
        cmd = mock_run.call_args[0][0]
        e_idx = cmd.index("-e")
        ssh_opts = cmd[e_idx + 1]
        assert str(key) in ssh_opts


# ──────────────────────────────────────────────────────────
# remove_local_source
# ──────────────────────────────────────────────────────────

class TestRemoveLocalSource:
    def test_removes_directory(self, src_dir: Path, mock_logger: MagicMock) -> None:
        assert src_dir.exists()
        sm.remove_local_source(src_dir, mock_logger)
        assert not src_dir.exists()

    def test_raises_on_missing_dir(
        self, tmp_path: Path, mock_logger: MagicMock
    ) -> None:
        non_existing = tmp_path / "ghost"
        with pytest.raises(FileNotFoundError):
            sm.remove_local_source(non_existing, mock_logger)


# ──────────────────────────────────────────────────────────
# create_virtual_symlink
# ──────────────────────────────────────────────────────────

class TestCreateVirtualSymlink:
    def test_creates_symlink_correctly(
        self, tmp_path: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        symlink_path = tmp_path / "Google_Drive_Pessoal_link"
        sm.create_virtual_symlink(symlink_path, dst_local, mock_logger)
        assert symlink_path.is_symlink()
        assert symlink_path.resolve() == dst_local.resolve()

    def test_raises_if_src_still_exists(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        # src_dir ainda existe (não foi deletado)
        with pytest.raises(FileExistsError):
            sm.create_virtual_symlink(src_dir, dst_local, mock_logger)

    def test_warns_when_dst_local_not_accessible(
        self, tmp_path: Path, mock_logger: MagicMock
    ) -> None:
        symlink_path = tmp_path / "virtual"
        offline_mount = Path("/mnt/offline/not/mounted")
        sm.create_virtual_symlink(symlink_path, offline_mount, mock_logger)
        assert symlink_path.is_symlink()
        mock_logger.warning.assert_called()


# ──────────────────────────────────────────────────────────
# migrate — fluxo completo
# ──────────────────────────────────────────────────────────

class TestMigrate:
    DST = "homelab@192.168.15.2:/mnt/lts/folder"

    def test_dry_run_does_nothing(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        """dry-run não deve alterar filesystem nem chamar rsync."""
        with patch.object(sm, "run_rsync") as mock_rsync, \
             patch.object(sm, "validate_transfer") as mock_val, \
             patch.object(sm, "remove_local_source") as mock_rm:
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=True, logger=mock_logger)
        assert rc == 0
        mock_rsync.assert_not_called()
        mock_val.assert_not_called()
        mock_rm.assert_not_called()
        assert src_dir.exists()  # origem intacta

    def test_success_path_removes_and_creates_symlink(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        """Caminho feliz: rsync ok + validação ok → remove local + cria symlink."""
        with patch.object(sm, "run_rsync", return_value=0), \
             patch.object(sm, "validate_transfer", return_value=True), \
             patch.object(sm, "remove_local_source", wraps=sm.remove_local_source):
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 0
        # origem foi removida, symlink no lugar
        assert not src_dir.exists() or src_dir.is_symlink()

    def test_rsync_failure_preserves_local(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        with patch.object(sm, "run_rsync", return_value=23), \
             patch.object(sm, "validate_transfer") as mock_val, \
             patch.object(sm, "remove_local_source") as mock_rm:
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 23
        mock_val.assert_not_called()
        mock_rm.assert_not_called()
        assert src_dir.exists()

    def test_validation_failure_preserves_local(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        with patch.object(sm, "run_rsync", return_value=0), \
             patch.object(sm, "validate_transfer", return_value=False), \
             patch.object(sm, "remove_local_source") as mock_rm:
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 2
        mock_rm.assert_not_called()
        assert src_dir.exists()

    def test_remove_failure_returns_error(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        with patch.object(sm, "run_rsync", return_value=0), \
             patch.object(sm, "validate_transfer", return_value=True), \
             patch.object(sm, "remove_local_source", side_effect=OSError("permission denied")):
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 3

    def test_symlink_failure_returns_error(
        self, src_dir: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        with patch.object(sm, "run_rsync", return_value=0), \
             patch.object(sm, "validate_transfer", return_value=True), \
             patch.object(sm, "remove_local_source"), \
             patch.object(sm, "create_virtual_symlink", side_effect=OSError("symlink error")):
            rc = sm.migrate(src_dir, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 4

    def test_returns_1_if_src_missing(
        self, tmp_path: Path, dst_local: Path, mock_logger: MagicMock
    ) -> None:
        missing = tmp_path / "not_here"
        rc = sm.migrate(missing, self.DST, dst_local, ssh_key=None, dry_run=False, logger=mock_logger)
        assert rc == 1


# ──────────────────────────────────────────────────────────
# main / CLI
# ──────────────────────────────────────────────────────────

class TestMain:
    def test_dry_run_by_default(self, src_dir: Path, dst_local: Path, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        argv = [
            "--src", str(src_dir),
            "--dst", "homelab@192.168.15.2:/mnt/lts/folder",
            "--dst-local", str(dst_local),
            "--log", str(log_file),
            # sem --execute → dry-run
        ]
        with patch.object(sm, "run_rsync") as mock_rsync, \
             patch("fcntl.flock"):
            rc = sm.main(argv)
        assert rc == 0
        mock_rsync.assert_not_called()

    def test_execute_flag_triggers_rsync(
        self, src_dir: Path, dst_local: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "test.log"
        argv = [
            "--src", str(src_dir),
            "--dst", "homelab@192.168.15.2:/mnt/lts/folder",
            "--dst-local", str(dst_local),
            "--log", str(log_file),
            "--execute",
        ]
        with patch.object(sm, "run_rsync", return_value=0) as mock_rsync, \
             patch.object(sm, "validate_transfer", return_value=True), \
             patch.object(sm, "remove_local_source"), \
             patch.object(sm, "create_virtual_symlink"), \
             patch("fcntl.flock"):
            rc = sm.main(argv)
        assert rc == 0
        mock_rsync.assert_called_once()
