"""
LTFS Log Rotation Agent — pilot LangGraph agent for homelab governance.

Tarefas:
  1. Verifica tamanho dos logs LTFS em /var/log/ (homelab) e via SSH na NAS
  2. Rotate qualquer log > SIZE_THRESHOLD_MB usando logrotate manual (gzip + truncate)
  3. Persiste resultado na memória compartilhada
  4. Rotation > CRITICAL_THRESHOLD_MB → risk=medium → requer aprovação Telegram

Uso como serviço (systemd) ou one-shot::

    python3 -m specialized_agents.ltfs_log_rotation_agent

Uso programático::

    from specialized_agents.ltfs_log_rotation_agent import LtfsLogRotationAgent
    agent = LtfsLogRotationAgent()
    result = agent.run(target="auto")  # auto-detecta logs a rotar

Env vars::

    DATABASE_URL, CHROMA_DB_PATH  — herdados de /etc/default/eddie-common
    LTFS_SIZE_THRESHOLD_MB        — default 10 (rotar se > X MB)
    LTFS_CRITICAL_THRESHOLD_MB    — default 100 (risk=medium se qualquer log > X MB)
    NAS_SSH_HOST                  — default root@192.168.15.4
"""
from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# Adiciona raiz do repo ao path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent

SIZE_THRESHOLD_MB    = float(os.environ.get("LTFS_SIZE_THRESHOLD_MB", "10"))
CRITICAL_THRESHOLD_MB = float(os.environ.get("LTFS_CRITICAL_THRESHOLD_MB", "100"))
NAS_SSH_HOST         = os.environ.get("NAS_SSH_HOST", "root@192.168.15.4")

HOMELAB_LOG_PATTERNS = [
    "/var/log/ltfs-lto6.log",
    "/var/log/ltfs-selfheal.log",
    "/var/log/ltfs-nfs-remount.log",
    "/var/log/homelab-disk-backup.log",
]

NAS_LOG_PATTERNS = [
    "/var/log/ltfs-lto6.log",
    "/var/log/ltfs-lto6b.log",
    "/var/log/ltfs-selfheal.log",
    "/var/log/ltfs-orchestrator.log",
]


class LogEntry(NamedTuple):
    path:   str
    size_mb: float
    host:   str  # "local" | "nas"


def _get_log_sizes() -> list[LogEntry]:
    entries: list[LogEntry] = []

    # Logs locais
    for p in HOMELAB_LOG_PATTERNS:
        try:
            sz = Path(p).stat().st_size / (1024 * 1024)
            entries.append(LogEntry(path=p, size_mb=round(sz, 2), host="local"))
        except FileNotFoundError:
            pass

    # Logs na NAS via SSH (non-fatal)
    try:
        out = subprocess.check_output(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             NAS_SSH_HOST, "stat -c '%n %s' " + " ".join(NAS_LOG_PATTERNS) + " 2>/dev/null || true"],
            text=True, timeout=10, stderr=subprocess.DEVNULL,
        )
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            parts = line.rsplit(None, 1)
            if len(parts) == 2:
                path_str, size_str = parts
                try:
                    sz = int(size_str) / (1024 * 1024)
                    entries.append(LogEntry(path=path_str, size_mb=round(sz, 2), host="nas"))
                except ValueError:
                    pass
    except Exception:
        pass

    return entries


def _rotate_local(path: str) -> str:
    """Gzip rotate: path → path.1.gz, truncate original."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return f"skip {path} (vazio ou inexistente)"
    ts = time.strftime("%Y%m%d_%H%M%S")
    archive = Path(f"{path}.{ts}.gz")
    with p.open("rb") as f_in, gzip.open(str(archive), "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    p.write_bytes(b"")
    return f"rotacionado {path} → {archive.name} ({archive.stat().st_size // 1024}KB)"


def _rotate_nas(path: str) -> str:
    """Rotate via SSH na NAS."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    archive = f"{path}.{ts}.gz"
    cmd = (
        f"gzip -c {path} > {archive} && truncate -s 0 {path} "
        f"&& echo 'rotacionado {path}'"
    )
    try:
        out = subprocess.check_output(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             NAS_SSH_HOST, cmd],
            text=True, timeout=30, stderr=subprocess.PIPE,
        )
        return out.strip() or f"rotacionado NAS:{path}"
    except subprocess.CalledProcessError as exc:
        return f"erro NAS:{path} — {exc.stderr[:200]}"


class LtfsLogRotationAgent(HomelabAgent):
    AGENT_ID    = "ltfs_log_rotation"
    ACTION_TYPE = "ltfs_rotate_logs"

    # risk_level é calculado dinamicamente em run(); base = low
    RISK_LEVEL  = "low"

    def _describe_work(self, state: AgentState) -> str:
        return (
            f"Verificar e rotacionar logs LTFS "
            f"(threshold={SIZE_THRESHOLD_MB}MB, critical={CRITICAL_THRESHOLD_MB}MB)"
        )

    def _execute_work(self, state: AgentState) -> dict:
        entries = _get_log_sizes()
        to_rotate = [e for e in entries if e.size_mb >= SIZE_THRESHOLD_MB]

        if not to_rotate:
            total = sum(e.size_mb for e in entries)
            return {
                "outcome": (
                    f"Nenhum log acima de {SIZE_THRESHOLD_MB}MB. "
                    f"Total verificado: {len(entries)} arquivo(s), {total:.1f}MB."
                ),
                "memory_fact": (
                    f"ltfs_log_rotation: {len(entries)} logs verificados, "
                    f"nenhuma rotação necessária (threshold={SIZE_THRESHOLD_MB}MB)"
                ),
            }

        results = []
        for entry in to_rotate:
            if entry.host == "local":
                results.append(_rotate_local(entry.path))
            else:
                results.append(_rotate_nas(entry.path))

        summary = "; ".join(results)
        memory_fact = (
            f"ltfs_log_rotation: {len(to_rotate)} log(s) rotacionado(s) "
            f"({', '.join(e.path.split('/')[-1] for e in to_rotate)})"
        )
        return {"outcome": summary, "memory_fact": memory_fact}


def main() -> int:
    """Entry point para execução one-shot via systemd ou linha de comando."""
    # Calcula risk_level antes de construir o agente
    entries = _get_log_sizes()
    has_critical = any(e.size_mb >= CRITICAL_THRESHOLD_MB for e in entries)
    risk = "medium" if has_critical else "low"

    # Sumário dos logs encontrados
    log_summary = ", ".join(
        f"{e.path.split('/')[-1]}={e.size_mb:.1f}MB@{e.host}"
        for e in entries if e.size_mb > 0
    ) or "nenhum log encontrado"
    print(f"[ltfs-log-rotation] Logs: {log_summary}")
    print(f"[ltfs-log-rotation] Risk calculado: {risk}")

    agent = LtfsLogRotationAgent()
    agent.RISK_LEVEL = risk

    result = agent.run(
        target="ltfs_logs",
        description=f"Rotacionar logs LTFS (threshold={SIZE_THRESHOLD_MB}MB). Logs: {log_summary}",
    )

    status = result.get("status", "unknown")
    approval = result.get("approval", "")
    thread_id = result.get("thread_id", "")

    if approval == "pending":
        print(f"[ltfs-log-rotation] Aguardando aprovação Telegram. thread_id={thread_id}")
        print(f"[ltfs-log-rotation] Para retomar: python3 -m specialized_agents.ltfs_log_rotation_agent --resume {thread_id}")
        return 0

    print(f"[ltfs-log-rotation] Status={status}")
    if result.get("outcome"):
        print(f"[ltfs-log-rotation] Resultado: {result['outcome']}")
    if result.get("error"):
        print(f"[ltfs-log-rotation] ERRO: {result['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", metavar="THREAD_ID", help="Retomar thread pausado")
    args = parser.parse_args()

    if args.resume:
        agent = LtfsLogRotationAgent()
        result = agent.resume(thread_id=args.resume)
        print(f"[ltfs-log-rotation] Retomado: status={result.get('status')}")
        if result.get("outcome"):
            print(f"[ltfs-log-rotation] Resultado: {result['outcome']}")
        sys.exit(0)

    sys.exit(main())
