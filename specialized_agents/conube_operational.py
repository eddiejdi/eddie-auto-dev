"""Coleta operacional da Conube para métricas Prometheus e relatórios."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _period_key_from_date(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.year, parsed.month


def _normalize_pending_docs(docs: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "source": source,
                "id": item.get("_id") or item.get("id"),
                "subject": item.get("Assunto") or item.get("assunto") or item.get("nome"),
                "status": item.get("Status") or item.get("status"),
                "due_date": item.get("Vencimento") or item.get("vencimento"),
                "month": item.get("mesCompetencia"),
                "year": item.get("anoCompetencia"),
                "responsible": item.get("Responsavel") or item.get("responsavel"),
            }
        )
    return items


def _normalize_last_periods(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": item.get("_id") or item.get("id"),
                "status": item.get("status"),
                "period_end": item.get("dataFimPeriodo"),
            }
        )
    return normalized


def _summarize_certificate(certificates: list[dict[str, Any]]) -> dict[str, Any]:
    if not certificates:
        return {"present": False, "expired": None, "latest_expiration": None}
    expirations = []
    for item in certificates:
        if not isinstance(item, dict):
            continue
        expiration = item.get("fimValidade")
        if expiration:
            expirations.append(expiration)
    latest_expiration = max(expirations) if expirations else None
    expired = None
    if latest_expiration:
        try:
            expired = datetime.fromisoformat(latest_expiration.replace("Z", "+00:00")) < datetime.now(timezone.utc)
        except ValueError:
            expired = None
    return {
        "present": True,
        "expired": expired,
        "latest_expiration": latest_expiration,
    }


def _open_period_keys(periods: list[dict[str, Any]]) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for item in periods:
        if str(item.get("status") or "").lower() != "aberto":
            continue
        key = _period_key_from_date(item.get("period_end"))
        if key:
            keys.add(key)
    return keys


def _dedupe_pending_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_source_rank = {"tarefas": 0, "impostos": 1, "impostos_obrigacoes": 2}
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = (
            item.get("subject"),
            item.get("due_date"),
            item.get("month"),
            item.get("year"),
            item.get("responsible"),
        )
        current = deduped.get(key)
        if current is None:
            deduped[key] = item
            continue
        current_rank = preferred_source_rank.get(str(current.get("source")), 99)
        new_rank = preferred_source_rank.get(str(item.get("source")), 99)
        if new_rank < current_rank:
            deduped[key] = item
    return list(deduped.values())


def _count_by_responsible(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("responsible") or "desconhecido").strip().lower() or "desconhecido"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _filter_items_for_open_periods(
    items: list[dict[str, Any]],
    period_keys: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    if not period_keys:
        return items
    filtered = []
    for item in items:
        year = item.get("year")
        month = item.get("month")
        if isinstance(year, int) and isinstance(month, int) and (year, month) in period_keys:
            filtered.append(item)
    return filtered


def build_snapshot_from_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    certificate = summary.get("certificate") or {}
    pending_items = report.get("pending_items") or []
    grouped = report.get("grouped_pending_items") or []

    top_overdue: list[dict[str, Any]] = []
    for item in pending_items:
        if isinstance(item, dict):
            top_overdue.append(
                {
                    "subject": item.get("subject") or item.get("Assunto") or "sem-assunto",
                    "source": item.get("source") or "pending_items",
                }
            )
    if not top_overdue:
        for item in grouped:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject") or "").strip()
            if not subject or subject.lower() == "estado atual da integracao":
                continue
            top_overdue.append(
                {
                    "subject": subject,
                    "source": str(item.get("responsible") or "grouped_pending_items"),
                }
            )

    periods: list[dict[str, Any]] = []
    for competence in summary.get("open_periods") or []:
        if isinstance(competence, dict):
            periods.append(competence)
        elif isinstance(competence, str):
            periods.append({"period": competence, "status": "aberto", "logs_count": 0})

    open_count = int(summary.get("open_periods_count") or 0)
    summary_payload = {
        "status": "ok",
        "open_periods_count": open_count,
        "pending_items_count": int(summary.get("pending_items_count") or 0),
        "overdue_items_count": int(summary.get("overdue_items_count") or 0),
        "relevant_items_count": int(summary.get("relevant_items_count") or 0),
        "client_actionable_items_count": int(summary.get("client_actionable_items_count") or 0),
        "accountant_owned_items_count": int(summary.get("accountant_owned_items_count") or 0),
        "top_overdue_items": top_overdue[:12],
        "certificate": certificate,
        "dashboard_loaded": bool((report.get("debug") or {}).get("authenticated")),
        "data_source": "cache",
    }
    audit_payload = {
        "status": "ok",
        "periods": periods,
        "open_periods_count": open_count,
        "closed_periods_count": int(summary.get("closed_periods_count") or 0),
    }
    billing_payload = {
        "status": "blocked" if certificate.get("expired") else "ok",
        "blocked_by_certificate": bool(certificate.get("expired")),
    }
    return {"summary": summary_payload, "audit": audit_payload, "billing": billing_payload}


def fetch_operational_snapshot(agent: Any, *, months_back: int = 12) -> dict[str, Any]:
    login_result = agent.login()
    if not login_result.get("authenticated"):
        raise RuntimeError(
            str(login_result.get("failure_reason") or "Login da Conube nao autenticou.")
        )
    if not agent._get_access_token():
        raise RuntimeError("Sessao autenticada sem access token disponivel.")

    endpoints = {
        "transactions_last_periods": ("client/v2", "transactions/last-periods"),
        "tarefas": ("client", "tarefas?concluida=false&responsavel=&limit=20&sort=vencimento:asc"),
        "impostos": ("client", "impostos?concluida=false&limit=20&sort=vencimento:asc"),
        "impostos_obrigacoes": (
            "client",
            "impostos-obrigacoes-acessorias?concluida=false&responsavel=&limit=20&sort=vencimento:asc",
        ),
        "certificados": ("client", "empresa/certificados-digitais"),
    }

    api_checks: dict[str, Any] = {}
    for key, (version, path) in endpoints.items():
        api_checks[key] = agent._authenticated_api_get(path, api_version=version)

    periods = _normalize_last_periods(api_checks.get("transactions_last_periods", []))
    audited: list[dict[str, Any]] = []
    for item in periods[:months_back]:
        period_end = item.get("period_end")
        if not period_end:
            continue
        status = agent.get_period_status(period_end)
        logs = status.get("logs") or []
        audited.append(
            {
                "period": f"{int(status.get('Ano', 0)):04d}-{int(status.get('Mes', 0)):02d}",
                "period_end": period_end,
                "period_id": status.get("_id") or item.get("id"),
                "status": status.get("Status"),
                "updated_at": status.get("updatedAt"),
                "attachments_count": len(status.get("_anexos") or []),
                "logs_count": len(logs),
                "last_log": logs[-1] if logs else None,
            }
        )

    pending_items: list[dict[str, Any]] = []
    for key in ("tarefas", "impostos", "impostos_obrigacoes"):
        payload = api_checks.get(key)
        if isinstance(payload, dict) and isinstance(payload.get("docs"), list):
            pending_items.extend(_normalize_pending_docs(payload["docs"], key))

    pending_items = _dedupe_pending_items(pending_items)
    open_period_keys = _open_period_keys(audited)
    overdue_items = [
        item
        for item in pending_items
        if str(item.get("status") or "").lower() in {"pendente", "atrasado", "aberto"}
    ]
    overdue_items.sort(key=lambda item: item.get("due_date") or "")
    relevant_items = _filter_items_for_open_periods(overdue_items, open_period_keys)
    certificate = _summarize_certificate(api_checks.get("certificados", []))
    open_periods = [item for item in audited if str(item.get("status") or "").lower() == "aberto"]
    responsible_counts = _count_by_responsible(pending_items)

    summary = {
        "status": "ok",
        "open_periods_count": len(open_periods),
        "open_periods": open_periods[:12],
        "pending_items_count": len(pending_items),
        "overdue_items_count": len(overdue_items),
        "relevant_items_count": len(relevant_items),
        "relevant_open_period_items": relevant_items[:12],
        "top_overdue_items": overdue_items[:12],
        "responsible_counts": responsible_counts,
        "client_actionable_items_count": responsible_counts.get("cliente", 0),
        "accountant_owned_items_count": responsible_counts.get("contador", 0),
        "certificate": certificate,
        "dashboard_loaded": True,
        "data_source": "api",
    }
    audit = {
        "status": "ok",
        "periods": audited,
        "open_periods_count": len([item for item in audited if str(item.get("status") or "").lower() == "aberto"]),
        "closed_periods_count": len([item for item in audited if str(item.get("status") or "").lower() == "fechado"]),
    }
    billing = {
        "status": "blocked" if certificate.get("expired") else "ok",
        "blocked_by_certificate": bool(certificate.get("expired")),
        "certificate_message_detected": bool(certificate.get("expired")),
        "checks": [],
    }
    return {"summary": summary, "audit": audit, "billing": billing}