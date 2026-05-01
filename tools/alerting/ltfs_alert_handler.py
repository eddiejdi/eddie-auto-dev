#!/usr/bin/env python3
"""Auxiliares para processar alertas LTFS e disparar diagnóstico/recuperação."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_FILE = Path(os.getenv("LTFS_ALERT_STATE_FILE", "/tmp/ltfs_alert_state.json"))
THROTTLE_SECONDS = int(os.getenv("LTFS_ALERT_THROTTLE", "300"))
LTFS_RECOVERY_SCRIPT = Path(__file__).resolve().parents[1] / "ltfs_recovery.py"
OLLAMA_ANALYSIS_ENABLED = os.getenv("LTFS_OLLAMA_ANALYSIS_ENABLED", "true").lower() not in {"0", "false", "no"}
OLLAMA_ANALYSIS_MODEL = os.getenv("LTFS_OLLAMA_ANALYSIS_MODEL", "").strip() or None

ALERT_MODE_MAP = {
    "ltfs-catalog": "catalog-check",
    "ltfs-drive": "drive-check",
    "ltfs-read": "drive-check",
    "ltfs-mount": "self-heal",
    "ltfs-io-hung": "self-heal",
    "ltfs-selfheal": "self-heal",
    "ltfs-drain": "diagnose",
}


def _load_state() -> dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text())
        return {k: float(v) for k, v in data.items()}
    except Exception:
        return {}


def _save_state(state: dict[str, float]) -> None:
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


def _run_ltfs_command(mode: str) -> tuple[bool, str, dict[str, Any]]:
    if not os.getenv("LTFS_RECOVERY_SSH_TARGET") and not LTFS_RECOVERY_SCRIPT.exists():
        return False, "script ltfs_recovery.py ausente", {}

    proc = subprocess.run(
        _build_ltfs_command(mode),
        capture_output=True,
        text=True,
        env=os.environ,
    )
    raw = proc.stdout.strip() or proc.stderr.strip()
    parsed: dict[str, Any] = {}
    if raw:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict):
            parsed = loaded
    if proc.returncode != 0:
        return False, raw, parsed
    return True, raw, parsed


def infer_ltfs_alert_type(alert_name: str) -> str | None:
    alert_map = {
        "LTFSCatalogUnavailable": "ltfs-catalog",
        "LTFSMountMissing": "ltfs-catalog",
        "LTFSMountDown": "ltfs-mount",
        "LTFSIOHung": "ltfs-io-hung",
        "LTFSSelfHealFailed": "ltfs-selfheal",
        "LTFSDrainStall": "ltfs-drain",
        "LTFSReadErrors": "ltfs-read",
        "LTFSReadOnly": "ltfs-read",
        "LTFSDriveIssues": "ltfs-drive",
    }
    return alert_map.get(alert_name)


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _extract_issue(parsed: dict[str, Any]) -> dict[str, Any]:
    return parsed.get("details", {}).get("issue") or {}


def _build_ollama_analysis(alert_type: str, alert_payload: dict[str, Any], diagnosis: dict[str, Any]) -> str | None:
    if not OLLAMA_ANALYSIS_ENABLED:
        return None

    prompt = (
        "Analise um incidente LTFS em producao e responda em portugues de forma objetiva. "
        "Inclua 3 linhas curtas: causa provavel, o que a automacao tentou e proximo passo operacional.\n\n"
        f"alert_type={alert_type}\n"
        f"alert_payload={_compact_json(alert_payload)}\n"
        f"diagnosis={_compact_json(diagnosis)}\n"
    )
    try:
        from tools.ollama_client import OllamaClient

        client = OllamaClient(model=OLLAMA_ANALYSIS_MODEL)
        return client.generate_text(prompt, num_predict=220, num_ctx=4096, timeout=120, small_request=False).strip() or None
    except Exception as exc:
        return f"Falha ao obter análise do Ollama: {exc}"


def process_ltfs_alert(alert_type: str, alert_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = alert_payload or {}
    if not _allowed_run(alert_type):
        return {
            "ok": True,
            "resolved": False,
            "throttled": True,
            "needs_attention": False,
            "message": f"Esperando throttle ({THROTTLE_SECONDS}s) antes de reenviar ações para {alert_type}.",
            "analysis": None,
        }

    mode = ALERT_MODE_MAP.get(alert_type, "diagnose")

    if mode == "catalog-check":
        ok, output, _parsed = _run_ltfs_command("check")
        if ok:
            return {
                "ok": True,
                "resolved": True,
                "throttled": False,
                "needs_attention": False,
                "message": f"Catálogo LTFS verificou sem falhas. {output}",
                "analysis": None,
            }
        ok_restore, output_restore, parsed_restore = _run_ltfs_command("catalog-restore")
        if ok_restore:
            ok_check, output_check, parsed_check = _run_ltfs_command("check")
            return {
                "ok": ok_check,
                "resolved": ok_check,
                "throttled": False,
                "needs_attention": not ok_check,
                "message": (
                    f"Catálogo restaurado. Status final: {output_check}"
                    if ok_check
                    else f"Recatalogação feita mas check final falhou: {output_check}"
                ),
                "analysis": None if ok_check else _build_ollama_analysis(alert_type, payload, parsed_check or parsed_restore),
            }
        restore_message = f"Falha ao restaurar catálogo: {output_restore}"
        if "Mountpoint LTFS inativo" in output_restore or "Mountpoint ausente" in output_restore:
            restore_message = f"Catálogo restaurado, mas o mount LTFS segue indisponível. {output_restore}"
        return {
            "ok": False,
            "resolved": False,
            "throttled": False,
            "needs_attention": True,
            "message": restore_message,
            "analysis": _build_ollama_analysis(alert_type, payload, parsed_restore),
        }

    if mode == "drive-check":
        ok, output, parsed = _run_ltfs_command("drive-check")
        return {
            "ok": ok,
            "resolved": ok,
            "throttled": False,
            "needs_attention": not ok,
            "message": f"Drive LTFS verificado. {output}",
            "analysis": None if ok else _build_ollama_analysis(alert_type, payload, parsed),
        }

    if mode == "self-heal":
        ok, output, parsed = _run_ltfs_command("self-heal")
        issue = _extract_issue(parsed)
        if ok:
            return {
                "ok": True,
                "resolved": True,
                "throttled": False,
                "needs_attention": False,
                "message": f"Self-heal concluído para {issue.get('title', alert_type)}. {output}",
                "analysis": None,
            }
        diagnosis_ok, diagnosis_output, diagnosis_parsed = _run_ltfs_command("diagnose")
        diagnosis = diagnosis_parsed or parsed
        issue = _extract_issue(diagnosis)
        return {
            "ok": False,
            "resolved": False,
            "throttled": False,
            "needs_attention": True,
            "message": (
                f"Self-heal falhou para {issue.get('title', alert_type)}. {output}"
                if issue
                else f"Self-heal falhou. {output or diagnosis_output}"
            ),
            "analysis": _build_ollama_analysis(alert_type, payload, diagnosis if diagnosis_ok else parsed),
        }

    ok, output, parsed = _run_ltfs_command("diagnose")
    issue = _extract_issue(parsed)
    return {
        "ok": ok,
        "resolved": False,
        "throttled": False,
        "needs_attention": not ok or not issue,
        "message": (
            f"Diagnóstico LTFS conhecido: {issue.get('title')}. {output}"
            if issue
            else f"Diagnóstico LTFS inconclusivo. {output}"
        ),
        "analysis": None if issue else _build_ollama_analysis(alert_type, payload, parsed),
    }


def handle_ltfs_alert(alert_type: str) -> str:
    result = process_ltfs_alert(alert_type)
    parts = [("✅ " if result["ok"] else "⚠️ ") + result["message"]]
    if result.get("analysis"):
        parts.append(f"Análise Ollama: {result['analysis']}")
    return "\n".join(parts)
