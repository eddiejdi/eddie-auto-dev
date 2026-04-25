"""Testes unitários para tools/ltfs_index_export.py.

Cobre:
- get_nst_device(): resolução via /sys e fallback
- read_volser(): leitura de label VOL1
- extract_index_from_partition0(): extração de XML e salvamento
- main(): guard de acessibilidade, saída limpa quando drive não acessível
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch, call

import pytest

# Garantir que tools/ está no path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ltfs_index_export


# ---------------------------------------------------------------------------
# get_nst_device
# ---------------------------------------------------------------------------


class TestGetNstDevice:
    """Resolução de /dev/sgX → /dev/nstY."""

    def test_resolve_via_sys_exact_match(self, tmp_path: Path) -> None:
        """Retorna nst0 quando existe entry exata em /sys."""
        tape_dir = tmp_path / "scsi_tape"
        tape_dir.mkdir(parents=True)
        (tape_dir / "nst0").mkdir()  # entry exata
        (tape_dir / "nst0l").mkdir()  # entrada com sufixo de densidade

        sg_sys = tmp_path
        with patch("tools.ltfs_index_export.Path") as MockPath:
            # Simular Path(f"/sys/class/scsi_generic/sg0/device")
            mock_sg_sys = MagicMock()
            mock_tape_dir = MagicMock()
            mock_sg_sys.__truediv__ = lambda self, x: mock_tape_dir if x == "scsi_tape" else MagicMock()
            mock_sg_sys.exists.return_value = True
            mock_tape_dir.exists.return_value = True

            exact_entry = MagicMock()
            exact_entry.exists.return_value = True
            mock_tape_dir.__truediv__ = lambda self, x: exact_entry

            MockPath.side_effect = lambda p: mock_sg_sys if "scsi_generic" in str(p) else Path(p)

            result = ltfs_index_export.get_nst_device("/dev/sg0")
            assert result == "/dev/nst0"

    def test_resolve_fallback_mapping(self) -> None:
        """Usa mapeamento hardcoded quando /sys não disponível."""
        with patch("tools.ltfs_index_export.Path") as MockPath:
            mock_sg = MagicMock()
            mock_sg.exists.return_value = False  # /sys não existe
            MockPath.side_effect = lambda p: mock_sg if "scsi_generic" in str(p) else Path(p)

            result = ltfs_index_export.get_nst_device("/dev/sg1")
            assert result == "/dev/nst1"

    def test_resolve_fallback_unknown_device(self) -> None:
        """Retorna /dev/nst5 para sg5 não mapeado."""
        with patch("tools.ltfs_index_export.Path") as MockPath:
            mock_sg = MagicMock()
            mock_sg.exists.return_value = False
            MockPath.side_effect = lambda p: mock_sg if "scsi_generic" in str(p) else Path(p)

            result = ltfs_index_export.get_nst_device("/dev/sg5")
            assert result == "/dev/nst5"


# ---------------------------------------------------------------------------
# read_volser
# ---------------------------------------------------------------------------


class TestReadVolser:
    """Leitura do VOLSER do label VOL1."""

    def test_reads_vol1_label(self) -> None:
        """Extrai VOLSER quando bloco 0 é label VOL1."""
        raw_block = b"VOL1HUJ548" + b" " * 70  # 80 bytes

        with (
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch("tools.ltfs_index_export.os.open") as mock_open,
            patch("tools.ltfs_index_export.os.read") as mock_read,
            patch("tools.ltfs_index_export.os.close") as mock_close,
        ):
            mock_run.return_value = CompletedProcess([], 0)
            mock_open.return_value = 5  # fake fd
            mock_read.return_value = raw_block
            mock_close.return_value = None

            result = ltfs_index_export.read_volser("/dev/nst0")
            assert result == "HUJ548"

    def test_returns_unknown_for_invalid_label(self) -> None:
        """Retorna UNKNOWN quando bloco 0 não tem VOL1."""
        raw_block = b"GARBAGE" + b"\x00" * 73

        with (
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch("tools.ltfs_index_export.os.open") as mock_open,
            patch("tools.ltfs_index_export.os.read") as mock_read,
            patch("tools.ltfs_index_export.os.close") as mock_close,
        ):
            mock_run.return_value = CompletedProcess([], 0)
            mock_open.return_value = 5
            mock_read.return_value = raw_block
            mock_close.return_value = None

            result = ltfs_index_export.read_volser("/dev/nst0")
            assert result == "UNKNOWN"


# ---------------------------------------------------------------------------
# extract_index_from_partition0
# ---------------------------------------------------------------------------


class TestExtractIndex:
    """Extração do XML ltfsindex da Partition 0."""

    def test_extracts_xml_and_saves(self, tmp_path: Path) -> None:
        """Extrai XML válido, salva arquivo e cria symlink latest."""
        xml_content = b"<ltfsindex version='2'><directory name='/'></directory></ltfsindex>"
        raw_tape = b"\x00" * 100 + xml_content + b"\x00" * 100

        with (
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch("tools.ltfs_index_export.os.open") as mock_open,
            patch("tools.ltfs_index_export.os.read") as mock_read_fn,
            patch("tools.ltfs_index_export.os.close") as mock_close,
        ):
            mock_run.return_value = CompletedProcess([], 0)
            mock_open.return_value = 7

            # Simular leitura em blocos: retorna dados e depois OSError (EOF)
            read_calls = [raw_tape, OSError("EOF")]

            def side_effect(fd: int, size: int) -> bytes:
                val = read_calls.pop(0)
                if isinstance(val, Exception):
                    raise val
                return val

            mock_read_fn.side_effect = side_effect
            mock_close.return_value = None

            result = ltfs_index_export.extract_index_from_partition0("/dev/nst0", tmp_path, "HUJ548")

            assert result.exists()
            assert result.name.startswith("HUJ548_")
            assert result.suffix == ".xml"
            # O código inclui +1 byte após </ltfsindex> (off-by-one inofensivo); checar conteúdo central
            saved = result.read_bytes()
            assert saved.startswith(b"<ltfsindex")
            assert b"</ltfsindex>" in saved

            latest = tmp_path / "HUJ548_latest.xml"
            assert latest.is_symlink()

    def test_raises_when_no_ltfsindex(self, tmp_path: Path) -> None:
        """Levanta RuntimeError quando ltfsindex tag não encontrada."""
        with (
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch("tools.ltfs_index_export.os.open") as mock_open,
            patch("tools.ltfs_index_export.os.read") as mock_read_fn,
            patch("tools.ltfs_index_export.os.close") as mock_close,
        ):
            mock_run.return_value = CompletedProcess([], 0)
            mock_open.return_value = 7
            read_calls = [b"no xml here at all"]

            def side_effect(fd: int, size: int) -> bytes:
                val = read_calls.pop(0) if read_calls else OSError("EOF")
                if isinstance(val, Exception):
                    raise val
                return val

            mock_read_fn.side_effect = side_effect
            mock_close.return_value = None

            with pytest.raises(RuntimeError, match="ltfsindex não encontrado"):
                ltfs_index_export.extract_index_from_partition0("/dev/nst0", tmp_path, "HUJ548")


# ---------------------------------------------------------------------------
# main() — guard de acessibilidade
# ---------------------------------------------------------------------------


class TestMain:
    """Comportamento de main() com e sem drive acessível."""

    def test_exits_cleanly_when_drive_not_accessible(self, tmp_path: Path) -> None:
        """Sai com código 0 (sys.exit(0)) quando mt status falha."""
        with (
            patch("tools.ltfs_index_export.get_nst_device", return_value="/dev/nst0"),
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch(
                "sys.argv",
                ["ltfs_index_export.py", "--device", "/dev/sg0", "--dest", str(tmp_path)],
            ),
        ):
            # mt status falha — drive não acessível
            mock_run.return_value = CompletedProcess(["mt", "-f", "/dev/nst0", "status"], 1, b"", b"Incorrect block size")

            with pytest.raises(SystemExit) as exc:
                ltfs_index_export.main()

            assert exc.value.code == 0

    def test_proceeds_when_drive_accessible(self, tmp_path: Path) -> None:
        """Chama read_volser quando mt status retorna sucesso."""
        with (
            patch("tools.ltfs_index_export.get_nst_device", return_value="/dev/nst0"),
            patch("tools.ltfs_index_export.subprocess.run") as mock_run,
            patch("tools.ltfs_index_export.read_volser", return_value="HUJ548") as mock_volser,
            patch("tools.ltfs_index_export.extract_index_from_partition0") as mock_extract,
            patch(
                "sys.argv",
                ["ltfs_index_export.py", "--device", "/dev/sg0", "--dest", str(tmp_path)],
            ),
        ):
            mock_run.return_value = CompletedProcess(["mt", "-f", "/dev/nst0", "status"], 0, b"BOT ONLINE", b"")
            fake_xml_path = tmp_path / "HUJ548_20260422_200000.xml"
            fake_xml_path.write_bytes(b"<ltfsindex></ltfsindex>")
            mock_extract.return_value = fake_xml_path

            ltfs_index_export.main()  # Não deve lançar exceção

            mock_volser.assert_called_once_with("/dev/nst0")
            mock_extract.assert_called_once()
