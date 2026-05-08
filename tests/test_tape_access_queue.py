"""Testes unitários para tape-access — gatekeeper FIFO exclusivo da fita LTO.

Valida que:
- O script existe e é executável
- status/queue/check funcionam sem erro quando fita livre
- tryrun com fita livre executa o comando
- tryrun com fita ocupada falha com exit 1 (sem bloquear)
- run enfileira e executa com acesso exclusivo (sem sobreposição)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TAPE_ACCESS = Path(__file__).parent.parent / "tools" / "tape-access"


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(TAPE_ACCESS)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ─── Disponibilidade do binário ──────────────────────────────────────────────

def test_tape_access_exists() -> None:
    assert TAPE_ACCESS.exists(), f"tape-access não encontrado em {TAPE_ACCESS}"


def test_tape_access_is_executable() -> None:
    assert os.access(TAPE_ACCESS, os.X_OK), "tape-access não é executável"


def test_version_output() -> None:
    r = _run(["version"])
    assert r.returncode == 0
    assert "tape-access" in r.stdout


# ─── status / queue / check quando livre ─────────────────────────────────────

def test_status_when_free() -> None:
    r = _run(["status"])
    assert r.returncode == 0
    assert "LIVRE" in r.stdout or "OCUPADA" in r.stdout


def test_queue_when_empty() -> None:
    r = _run(["queue"])
    assert r.returncode == 0
    assert "QUEUE" in r.stdout


def test_check_exit_0_when_free() -> None:
    """check deve retornar 0 se a fita estiver livre."""
    r = _run(["check"])
    # Se ocupada por outro teste concorrente aceita exit 1 também
    assert r.returncode in (0, 1)


# ─── tryrun quando livre ──────────────────────────────────────────────────────

def test_tryrun_executes_when_free() -> None:
    r = _run(["tryrun", "--", "echo", "tape-access-ok"])
    assert r.returncode == 0


# ─── tryrun quando ocupado ───────────────────────────────────────────────────

def test_tryrun_fails_when_occupied() -> None:
    """Inicia um holder de 4s, verifica que tryrun falha imediatamente."""
    holder = subprocess.Popen(
        [str(TAPE_ACCESS), "run", "--name", "test-holder", "--timeout", "10",
         "--", "sleep", "4"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(1.0)  # aguarda holder adquirir o lock

        r = _run(["tryrun", "--name", "test-tryrun-fail", "--", "echo", "nao-devia-rodar"])
        assert r.returncode == 1, (
            f"tryrun deveria falhar com exit 1 mas retornou {r.returncode}"
        )
        assert "OCUPADO" in r.stderr
    finally:
        holder.terminate()
        holder.wait(timeout=6)


# ─── run: fila FIFO (sem sobreposição) ───────────────────────────────────────

def test_run_queue_no_overlap() -> None:
    """Dois processos simultâneos nunca rodam ao mesmo tempo.

    Estratégia: gravar timestamp de início e fim em arquivos distintos,
    depois verificar que os intervalos não se sobrepõem.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        log_a = os.path.join(tmp, "a.log")
        log_b = os.path.join(tmp, "b.log")

        cmd_a = [
            str(TAPE_ACCESS), "run", "--name", "test-A", "--timeout", "20",
            "--", "bash", "-c",
            f"echo START_A:$(date +%s%N) > {log_a}; sleep 2; echo END_A:$(date +%s%N) >> {log_a}",
        ]
        cmd_b = [
            str(TAPE_ACCESS), "run", "--name", "test-B", "--timeout", "20",
            "--", "bash", "-c",
            f"echo START_B:$(date +%s%N) > {log_b}; sleep 1; echo END_B:$(date +%s%N) >> {log_b}",
        ]

        pa = subprocess.Popen(cmd_a)
        time.sleep(0.3)
        pb = subprocess.Popen(cmd_b)

        pa.wait(timeout=30)
        pb.wait(timeout=30)

        assert pa.returncode == 0, "Processo A falhou"
        assert pb.returncode == 0, "Processo B falhou"

        def _parse_ns(path: str, prefix: str) -> int:
            with open(path) as f:
                for line in f:
                    if line.startswith(prefix):
                        return int(line.strip().split(":")[1])
            raise AssertionError(f"Marcador {prefix} não encontrado em {path}")

        start_a = _parse_ns(log_a, "START_A")
        end_a   = _parse_ns(log_a, "END_A")
        start_b = _parse_ns(log_b, "START_B")
        end_b   = _parse_ns(log_b, "END_B")

        # Não pode haver sobreposição: B começa depois que A termina, ou vice-versa
        overlap = (start_a < end_b) and (start_b < end_a)
        assert not overlap, (
            f"Sobreposição detectada!\n"
            f"A: {start_a} → {end_a}\n"
            f"B: {start_b} → {end_b}"
        )
