#!/usr/bin/env python3
"""Auxiliares para processar alertas LTFS e disparar ltfs_recovery."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

STATE_FILE = Path(os.getenv("LTFS_ALERT_STATE_FILE", "/tmp/ltfs_alert_state.json"))
THROTTLE_SECONDS = int(os.getenv("LTFS_ALERT_THROTTLE", "300"))
LTFS_RECOVERY_SCRIPT = Path(__file__).resolve().parents[1] / "ltfs_recovery.py"


def _load_state() -> Dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text())
        return {k: float(v) for k, v in data.items()}
    except Exception:
        return {}


def _save_state(state: Dict[str, float]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def _allowed_run(alert_type: str) -> bool:
    state = _load_state()
    now = datetime.now().timestamp()
    last = state.get(alert_type)
    if last and now - last < THROTTLE_SECONDS:
        return False
    state[alert_type] = now
    _save_state(state)
    return True


def _build_ltfs_command(mode: str) -> list[str]:
    ssh_target = os.getenv("LTFS_RECOVERY_SSH_TARGET", "").strip()
    remote_script = os.getenv("LTFS_RECOVERY_REMOTE_SCRIPT", "/usr/local/tools/ltfs_recovery.py")
    if ssh_target:
        ssh_password = os.getenv("LTFS_RECOVERY_SSH_PASSWORD", "").strip()
        ssh_cmd = ["ssh"]
        if not ssh_password:
            ssh_cmd.extend(["-o", "BatchMode=yes"])
        ssh_cmd.extend([ssh_target, "python3", remote_script, f"--{mode}"])
        if ssh_password:
            return ["sshpass", "-p", ssh_password, *ssh_cmd]
        return ssh_cmd
    return ["python3", str(LTFS_RECOVERY_SCRIPT), f"--{mode}"]


def _run_ltfs_command(mode: str) -> Tuple[bool, str]:
    if not os.getenv("LTFS_RECOVERY_SSH_TARGET") and not LTFS_RECOVERY_SCRIPT.exists():
        return False, "script ltfs_recovery.py ausente"
    proc = subprocess.run(
        _build_ltfs_command(mode),
        capture_output=True,
        text=True,
        env=os.environ,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, proc.stdout.strip()


def handle_ltfs_alert(alert_type: str) -> str:
    if not _allowed_run(alert_type):
        return f"⚠️ Esperando throttle ({THROTTLE_SECONDS}s) antes de reenviar ações para {alert_type}."

    if alert_type == "ltfs-catalog":
        ok, output = _run_ltfs_command("check")
        if ok:
            return f"✅ Catálogo LTFS verificou sem falhas.\n{output}"
        ok_restore, output_restore = _run_ltfs_command("catalog-restore")
        if not ok_restore:
            if "Mountpoint LTFS inativo" in output_restore or "Mountpoint ausente" in output_restore:
                return f"⚠️ Catálogo restaurado, mas o mount LTFS segue indisponível.\n{output_restore}"
            return f"❌ Falha ao restaurar catálogo: {output_restore}"
        ok_check, output_check = _run_ltfs_command("check")
        return f"♻️ Catálogo restaurado. Status final: {output_check}" if ok_check else f"⚠️ Recatalogação feita mas check final falhou: {output_check}"

    if alert_type in {"ltfs-drive", "ltfs-read"}:
        ok, output = _run_ltfs_command("drive-check")
        emoji = "✅" if ok else "⚠️"
        return f"{emoji} Drive LTFS verificado.\n{output}"

    return f"ℹ️ Alert type {alert_type} não mapeado para recuperação automática."
