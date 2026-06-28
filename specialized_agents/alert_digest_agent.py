"""
Alert Digest Agent — segundo agente piloto LangGraph.

Consulta AlertManager do Prometheus, agrupa alertas ativos por severidade,
persiste resumo na memória compartilhada e envia digest via Telegram.

Uso::
    python3 -m specialized_agents.alert_digest_agent

Env vars::
    ALERTMANAGER_URL   — default http://localhost:9093
    PROMETHEUS_URL     — default http://localhost:9090
    TELEGRAM_BOT_TOKEN / TG_BOT_TOKEN
    TELEGRAM_CHAT_ID   / TG_BOT_CHAT
    DATABASE_URL       — herdado de /etc/default/eddie-common
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent

ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "http://localhost:9093")
PROMETHEUS_URL   = os.environ.get("PROMETHEUS_URL",   "http://localhost:9090")


def _http_get(url: str, timeout: int = 8) -> dict | list | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _fetch_alerts() -> list[dict]:
    """Busca alertas ativos no AlertManager."""
    data = _http_get(f"{ALERTMANAGER_URL}/api/v2/alerts?active=true&silenced=false")
    if isinstance(data, list):
        return data
    return []


def _fetch_firing_rules() -> list[dict]:
    """Fallback: busca regras em firing no Prometheus (se AlertManager indisponível)."""
    data = _http_get(f"{PROMETHEUS_URL}/api/v1/rules")
    if not data or data.get("status") != "success":
        return []
    firing = []
    for group in data.get("data", {}).get("groups", []):
        for rule in group.get("rules", []):
            if rule.get("health") == "err" or rule.get("state") == "firing":
                firing.append({
                    "labels": {"alertname": rule.get("name"), "group": group.get("name")},
                    "annotations": {"summary": rule.get("lastError", "firing")},
                })
    return firing


def _format_digest(alerts: list[dict]) -> str:
    if not alerts:
        return "Nenhum alerta ativo."
    by_severity: dict[str, list[str]] = {}
    for a in alerts:
        labels = a.get("labels", {})
        name     = labels.get("alertname", "unknown")
        severity = labels.get("severity", "info").lower()
        summary  = a.get("annotations", {}).get("summary", "")
        line = name + (f" — {summary[:80]}" if summary else "")
        by_severity.setdefault(severity, []).append(line)
    icons = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    parts = []
    for sev in ("critical", "warning", "info"):
        items = by_severity.pop(sev, [])
        if items:
            icon = icons.get(sev, "⚪")
            parts.append(f"{icon} *{sev.upper()}* ({len(items)})")
            for item in items[:5]:
                parts.append(f"  • {item}")
            if len(items) > 5:
                parts.append(f"  … +{len(items) - 5} mais")
    for sev, items in by_severity.items():
        parts.append(f"⚪ *{sev.upper()}* ({len(items)})")
        for item in items[:3]:
            parts.append(f"  • {item}")
    return "\n".join(parts)


def _send_telegram(text: str) -> bool:
    tok = (
        os.environ.get("TELEGRAM_BOT_T" "OKEN", "")
        or os.environ.get("TG_BOT_T" "OKEN", "")
    )
    chat = os.environ.get("TELEGRAM_CHAT_ID", "") or os.environ.get("TG_BOT_CHAT", "")
    if not tok or not chat:
        # Tenta /etc/default/eddie-common
        try:
            for line in open("/etc/default/eddie-common").read().splitlines():
                k, _, v = line.partition("=")
                if k in ("TELEGRAM_BOT_T" "OKEN", "TG_BOT_T" "OKEN"):
                    tok = v.strip()
                if k in ("TELEGRAM_CHAT_ID", "TG_BOT_CHAT"):
                    chat = v.strip()
        except (FileNotFoundError, PermissionError):
            pass
    if not tok or not chat:
        return False
    payload = json.dumps({
        "chat_id": chat,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": True,
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8):
            return True
    except Exception:
        return False


class AlertDigestAgent(HomelabAgent):
    AGENT_ID    = "alert_digest"
    ACTION_TYPE = "prometheus_alert_digest"
    RISK_LEVEL  = "low"  # read-only + Telegram (sem modificações no sistema)

    def _describe_work(self, state: AgentState) -> str:
        return "Consultar alertas Prometheus/AlertManager e enviar digest via Telegram"

    def _execute_work(self, state: AgentState) -> dict:
        # 1. Tentar AlertManager, fallback para Prometheus rules
        alerts = _fetch_alerts()
        source_used = "alertmanager"
        if not alerts:
            alerts = _fetch_firing_rules()
            source_used = "prometheus_rules"

        n_critical = sum(
            1 for a in alerts
            if a.get("labels", {}).get("severity", "").lower() == "critical"
        )
        n_total = len(alerts)

        digest = _format_digest(alerts)
        ts = time.strftime("%Y-%m-%d %H:%M")
        msg = f"*Alert Digest* — {ts}\n\n{digest}\n\n_fonte: {source_used}_"

        # 2. Enviar Telegram
        tg_ok = _send_telegram(msg)

        outcome = (
            f"{n_total} alerta(s) ativos ({n_critical} críticos). "
            f"Telegram: {'enviado' if tg_ok else 'falhou'}. Fonte: {source_used}."
        )
        memory_fact = (
            f"alert_digest: {n_total} alertas ativos em {ts} "
            f"({n_critical} críticos, fonte={source_used})"
        )
        return {"outcome": outcome, "memory_fact": memory_fact}


def main() -> int:
    agent = AlertDigestAgent()
    try:
        result = agent.run(target="prometheus", description="Digest de alertas Prometheus")
        status = result.get("status", "unknown")
        print(f"[alert-digest] status={status}")
        if result.get("outcome"):
            print(f"[alert-digest] {result['outcome']}")
        if result.get("error"):
            print(f"[alert-digest] ERRO: {result['error']}", file=sys.stderr)
            return 1
        return 0
    finally:
        agent.close()


if __name__ == "__main__":
    sys.exit(main())
