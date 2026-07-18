#!/usr/bin/env python3
"""incident_notify.py — Comunicação obrigatória de incidentes em hooks.

Política global: nunca engolir erro/fallback sem registrar incidente visível.

Canais (sempre stderr + arquivo local; Telegram se configurado):
  - stderr (imediato no terminal do commit/agent)
  - .git/hook_incidents.log (auditoria local)
  - artifacts/hook_incidents/ (JSON por evento)
  - Telegram (opcional: TELEGRAM_BOT_TOKEN + ADMIN_CHAT_ID ou TRADING_TELEGRAM_*)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = REPO_ROOT / ".git" / "hook_incidents.log"
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "hook_incidents"


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append_log(line: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{_ts()}] {line}\n")
    except OSError as exc:
        print(f"[incident_notify] falha ao gravar log: {exc}", file=sys.stderr)


def _write_artifact(payload: dict[str, Any]) -> Path | None:
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        path = ARTIFACT_DIR / f"incident_{int(time.time())}_{os.getpid()}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
    except OSError as exc:
        print(f"[incident_notify] falha ao gravar artifact: {exc}", file=sys.stderr)
        return None


def _telegram_send(text: str) -> bool:
    token = (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("HOOK_INCIDENT_TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    chat = (
        os.environ.get("HOOK_INCIDENT_CHAT_ID")
        or os.environ.get("ADMIN_CHAT_ID")
        or os.environ.get("TRADING_TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    if not token or not chat or token.startswith("your_"):
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {
            "chat_id": chat,
            "text": text[:3900],
            "disable_web_page_preview": "true",
        }
    ).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=12) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[incident_notify] Telegram falhou: {exc}", file=sys.stderr)
        return False


def emit_incident(
    source: str,
    summary: str,
    *,
    severity: str = "error",
    details: str = "",
    context: dict[str, Any] | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    """Registra e comunica um incidente de hook/agente.

    Nunca engole: no mínimo imprime em stderr e grava log local.
    """
    severity = (severity or "error").lower()
    banner = {
        "critical": "🚨 INCIDENTE CRÍTICO",
        "error": "❌ INCIDENTE",
        "warn": "⚠️ INCIDENTE",
        "warning": "⚠️ INCIDENTE",
        "info": "ℹ️ INCIDENTE",
    }.get(severity, "❌ INCIDENTE")

    lines = [
        f"{banner} [{source}]",
        f"  resumo: {summary}",
    ]
    if details:
        for dline in str(details).strip().splitlines()[:20]:
            lines.append(f"  {dline}")
    if context:
        try:
            ctx = json.dumps(context, ensure_ascii=False, default=str)
        except Exception:
            ctx = str(context)
        lines.append(f"  contexto: {ctx[:500]}")
    lines.append("  política: erros silenciosos / fallbacks sem comunicação são proibidos")

    message = "\n".join(lines)
    print(message, file=sys.stderr)
    _append_log(f"{severity.upper()} source={source} summary={summary}")

    payload = {
        "timestamp": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "severity": severity,
        "summary": summary,
        "details": details,
        "context": context or {},
        "exit_code": exit_code,
        "cwd": str(Path.cwd()),
        "repo": str(REPO_ROOT),
    }
    artifact = _write_artifact(payload)
    if artifact:
        print(f"  artifact: {artifact}", file=sys.stderr)

    tg_text = (
        f"{banner}\n"
        f"source: {source}\n"
        f"{summary}\n"
        + (f"\n{details[:800]}\n" if details else "")
        + f"\nrepo: {REPO_ROOT.name}"
    )
    tg_ok = _telegram_send(tg_text)
    payload["telegram_sent"] = tg_ok
    if not tg_ok:
        print(
            "  (Telegram não enviado — defina TELEGRAM_BOT_TOKEN + ADMIN_CHAT_ID "
            "para alerta remoto; incidente já está em stderr/log/artifact)",
            file=sys.stderr,
        )

    if exit_code is not None:
        raise SystemExit(exit_code)
    return payload


def main(argv: list[str]) -> int:
    """CLI: python3 incident_notify.py --source X --summary Y [--details Z] [--severity error]"""
    import argparse

    p = argparse.ArgumentParser(description="Emite incidente de hook")
    p.add_argument("--source", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--details", default="")
    p.add_argument("--severity", default="error")
    p.add_argument("--exit-code", type=int, default=None)
    args = p.parse_args(argv)
    emit_incident(
        args.source,
        args.summary,
        severity=args.severity,
        details=args.details,
        exit_code=args.exit_code,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
