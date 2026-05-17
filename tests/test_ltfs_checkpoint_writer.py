"""
Testes unitários para tools/ltfs_checkpoint_writer.py

Cobre:
  - build_file_manifest: manifest correto de diretório
  - _save_journal / _load_journal: escrita atômica e leitura
  - _find_incomplete_session: detecta sessão in_progress, ignora completed
  - sha256_file: hash correto
  - verify_files_on_tape: done/missing/mismatch por arquivo
  - cmd_run: fluxo completo com fita simulada (sem SSH real)
  - cmd_recover: retomada com arquivos "writing" resetados
"""

import hashlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ─── Patch de módulos de sistema antes do import ─────────────────────────────

# Cria stub de subprocess para evitar chamadas reais durante import
_subprocess_stub = types.ModuleType("subprocess")
_subprocess_stub.run = MagicMock()
_subprocess_stub.CompletedProcess = MagicMock
sys.modules.setdefault("subprocess", _subprocess_stub)

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import ltfs_checkpoint_writer as cw  # noqa: E402


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_journal(tmp_path):
    """Journal dir temporário isolado por teste."""
    jdir = tmp_path / "journal"
    jdir.mkdir()
    (jdir / "sessions").mkdir()
    original = cw.JOURNAL_DIR
    cw.JOURNAL_DIR = jdir
    yield jdir
    cw.JOURNAL_DIR = original


@pytest.fixture()
def snapshot_dir(tmp_path):
    """Cria snapshot fake com alguns arquivos."""
    snap = tmp_path / "src" / "rpa4all-snapshot-20260516T120000Z"
    snap.mkdir(parents=True)
    (snap / "file_a.tar.gz").write_bytes(b"conteudo_a" * 100)
    (snap / "subdir").mkdir()
    (snap / "subdir" / "file_b.tar.gz").write_bytes(b"conteudo_b" * 200)
    return snap


# ─── Testes: build_file_manifest ─────────────────────────────────────────────

def test_build_file_manifest(snapshot_dir):
    manifest = cw.build_file_manifest(snapshot_dir)
    assert "file_a.tar.gz" in manifest
    assert "subdir/file_b.tar.gz" in manifest
    for fdata in manifest.values():
        assert fdata["status"] == "pending"
        assert fdata["sha256_src"] is None
        assert fdata["sha256_tape"] is None
        assert fdata["size"] > 0


def test_build_file_manifest_vazio(tmp_path):
    snap = tmp_path / "snap_vazio"
    snap.mkdir()
    assert cw.build_file_manifest(snap) == {}


# ─── Testes: journal ─────────────────────────────────────────────────────────

def test_save_and_load_journal(tmp_journal):
    path = cw._session_path("test123")
    data = {"session_id": "test123", "status": "in_progress", "snapshots": {}}
    cw._save_journal(path, data)
    loaded = cw._load_journal(path)
    assert loaded == data


def test_save_journal_atomico(tmp_journal):
    """Verifica que o .tmp é renomeado e não sobra artefato."""
    path = cw._session_path("atomic_test")
    cw._save_journal(path, {"status": "completed"})
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()


# ─── Testes: _find_incomplete_session ────────────────────────────────────────

def test_find_incomplete_session_detects_in_progress(tmp_journal):
    path = cw._session_path("20260516T100000")
    cw._save_journal(path, {"status": "in_progress", "session_id": "20260516T100000"})
    found = cw._find_incomplete_session()
    assert found == path


def test_find_incomplete_session_ignora_completed(tmp_journal):
    path = cw._session_path("20260516T110000")
    cw._save_journal(path, {"status": "completed", "session_id": "20260516T110000"})
    assert cw._find_incomplete_session() is None


def test_find_incomplete_session_retorna_mais_recente(tmp_journal):
    for sid, status in [("20260516T080000", "completed"), ("20260516T090000", "failed")]:
        cw._save_journal(cw._session_path(sid), {"status": status, "session_id": sid})
    found = cw._find_incomplete_session()
    assert found is not None
    assert "20260516T090000" in found.name


# ─── Testes: sha256_file ─────────────────────────────────────────────────────

def test_sha256_file(tmp_path):
    f = tmp_path / "test.bin"
    content = b"dados de teste"
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert cw.sha256_file(f) == expected


# ─── Testes: verify_files_on_tape ────────────────────────────────────────────

@pytest.fixture()
def journal_for_verify(tmp_journal, tmp_path):
    """Journal com snapshot de 2 arquivos pendentes."""
    content_a = b"arquivo_a" * 50
    content_b = b"arquivo_b" * 80

    src = tmp_path / "snap"
    src.mkdir()
    (src / "file_a.bin").write_bytes(content_a)
    (src / "file_b.bin").write_bytes(content_b)

    snap_data = {
        "status": "pending",
        "synced_at": None,
        "files": {
            "file_a.bin": {
                "status": "pending", "size": len(content_a),
                "sha256_src": hashlib.sha256(content_a).hexdigest(),
                "sha256_tape": None, "written_at": None,
            },
            "file_b.bin": {
                "status": "pending", "size": len(content_b),
                "sha256_src": hashlib.sha256(content_b).hexdigest(),
                "sha256_tape": None, "written_at": None,
            },
        },
    }
    journal = {
        "session_id": "verify_test",
        "status": "in_progress",
        "source_dir": str(tmp_path),
        "tape_target": str(tmp_path / "tape"),
        "snapshots": {"snap": snap_data},
    }
    journal_path = cw._session_path("verify_test")
    cw._save_journal(journal_path, journal)
    return journal, journal_path, src, snap_data, content_a, content_b, tmp_path


def test_verify_ok(journal_for_verify, tmp_path):
    journal, journal_path, src, snap_data, content_a, content_b, base = journal_for_verify
    dest = base / "tape" / "snap"
    dest.mkdir(parents=True)
    (dest / "file_a.bin").write_bytes(content_a)
    (dest / "file_b.bin").write_bytes(content_b)

    ok, fail = cw.verify_files_on_tape("snap", snap_data, src, dest, journal_path, journal)
    assert ok == 2
    assert fail == 0
    assert snap_data["files"]["file_a.bin"]["status"] == "done"
    assert snap_data["files"]["file_b.bin"]["status"] == "done"


def test_verify_missing_file(journal_for_verify, tmp_path):
    journal, journal_path, src, snap_data, content_a, content_b, base = journal_for_verify
    dest = base / "tape" / "snap"
    dest.mkdir(parents=True)
    (dest / "file_a.bin").write_bytes(content_a)
    # file_b.bin ausente na fita

    ok, fail = cw.verify_files_on_tape("snap", snap_data, src, dest, journal_path, journal)
    assert ok == 1
    assert fail == 1
    assert snap_data["files"]["file_b.bin"]["status"] == "failed"


def test_verify_mismatch(journal_for_verify, tmp_path):
    journal, journal_path, src, snap_data, content_a, content_b, base = journal_for_verify
    dest = base / "tape" / "snap"
    dest.mkdir(parents=True)
    (dest / "file_a.bin").write_bytes(content_a)
    (dest / "file_b.bin").write_bytes(b"conteudo_corrompido")  # mismatch SHA256

    ok, fail = cw.verify_files_on_tape("snap", snap_data, src, dest, journal_path, journal)
    assert ok == 1
    assert fail == 1
    assert snap_data["files"]["file_b.bin"]["status"] == "failed"


def test_verify_skip_done(journal_for_verify, tmp_path):
    """Arquivos já 'done' no journal são pulados sem verificar a fita."""
    journal, journal_path, src, snap_data, content_a, content_b, base = journal_for_verify
    snap_data["files"]["file_a.bin"]["status"] = "done"
    snap_data["files"]["file_b.bin"]["status"] = "done"

    dest = base / "tape" / "snap"
    dest.mkdir(parents=True)
    # Não cria os arquivos na fita — não devem ser acessados

    ok, fail = cw.verify_files_on_tape("snap", snap_data, src, dest, journal_path, journal)
    assert ok == 2
    assert fail == 0


# ─── Testes: cmd_run (fluxo integrado com mocks) ─────────────────────────────

def _make_completed_proc(returncode=0):
    m = MagicMock()
    m.returncode = returncode
    return m


def test_cmd_run_sem_snapshots(tmp_journal, tmp_path, monkeypatch):
    src = tmp_path / "backups"
    src.mkdir()
    tape = tmp_path / "tape"
    tape.mkdir()
    (tape / ".checkpoint-probe")  # não precisa existir

    monkeypatch.setattr(cw, "BACKUPS_SRC", str(src))
    monkeypatch.setattr(cw, "TAPE_TARGET", str(tape))
    monkeypatch.setattr(cw, "TAPE_CIFS_MOUNT", str(tape))

    with patch("subprocess.run", return_value=_make_completed_proc(0)):
        result = cw.cmd_run(MagicMock())

    assert result == 0  # sem snapshots = sucesso sem fazer nada


def test_cmd_run_fluxo_completo(tmp_journal, snapshot_dir, tmp_path, monkeypatch):
    """Verifica que run cria journal, copia e verifica arquivos."""
    src_dir = snapshot_dir.parent
    tape_target = tmp_path / "tape" / "backups"
    tape_target.mkdir(parents=True)
    tape_cifs = tmp_path / "tape"

    monkeypatch.setattr(cw, "BACKUPS_SRC", str(src_dir))
    monkeypatch.setattr(cw, "TAPE_TARGET", str(tape_target))
    monkeypatch.setattr(cw, "TAPE_CIFS_MOUNT", str(tape_cifs))

    snap_name = snapshot_dir.name
    snap_dest = tape_target / snap_name
    snap_dest.mkdir(parents=True)

    # Simula rsync copiando os arquivos para o destino
    def fake_rsync(*args, **kwargs):
        snap_src = snapshot_dir
        for f in snap_src.rglob("*"):
            if f.is_file():
                rel = f.relative_to(snap_src)
                dst = snap_dest / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(f.read_bytes())
        m = MagicMock()
        m.returncode = 0
        return m

    def fake_subprocess_run(cmd, **kwargs):
        if isinstance(cmd, list) and "rsync" in cmd:
            return fake_rsync(cmd)
        m = MagicMock()
        m.returncode = 0
        m.stdout = MagicMock()
        m.stdout.strip = MagicMock(return_value="active")
        return m

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = cw.cmd_run(MagicMock())

    assert result == 0

    # Journal deve existir e estar completed
    sessions = list((tmp_journal / "sessions").glob("session_*.json"))
    assert len(sessions) == 1
    data = cw._load_journal(sessions[0])
    assert data["status"] == "completed"
    assert data["snapshots"][snap_name]["status"] == "done"


# ─── Testes: cmd_recover ─────────────────────────────────────────────────────

def test_cmd_recover_sem_sessao_incompleta(tmp_journal, monkeypatch):
    result = cw.cmd_recover(MagicMock())
    assert result == 0


def test_cmd_recover_reseta_writing(tmp_journal, tmp_path, monkeypatch):
    """Arquivos 'writing' no journal devem ser resetados para 'pending'."""
    src_dir = tmp_path / "src"
    tape_target = tmp_path / "tape"
    src_dir.mkdir()
    tape_target.mkdir()

    snap = src_dir / "rpa4all-snapshot-20260516T000000Z"
    snap.mkdir()
    content = b"teste" * 100
    (snap / "arq.bin").write_bytes(content)

    snap_dest = tape_target / snap.name
    snap_dest.mkdir()
    (snap_dest / "arq.bin").write_bytes(content)

    journal = {
        "session_id": "20260516T000000",
        "started_at": "2026-05-16T00:00:00Z",
        "completed_at": None,
        "status": "in_progress",
        "source_dir": str(src_dir),
        "tape_target": str(tape_target),
        "snapshots": {
            snap.name: {
                "status": "in_progress",
                "synced_at": None,
                "files": {
                    "arq.bin": {
                        "status": "writing",
                        "size": len(content),
                        "sha256_src": hashlib.sha256(content).hexdigest(),
                        "sha256_tape": None,
                        "written_at": None,
                    }
                },
            }
        },
    }
    journal_path = cw._session_path("20260516T000000")
    cw._save_journal(journal_path, journal)

    monkeypatch.setattr(cw, "TAPE_CIFS_MOUNT", str(tmp_path / "tape"))

    def fake_subprocess_run(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = MagicMock()
        m.stdout.strip = MagicMock(return_value="active")
        return m

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        cw.cmd_recover(MagicMock())

    recovered = cw._load_journal(journal_path)
    # O arquivo que era "writing" não deve mais estar nesse estado
    final_status = recovered["snapshots"][snap.name]["files"]["arq.bin"]["status"]
    assert final_status != "writing"
