"""Remediação operacional da Conube — fecha períodos e trata pendências do cliente."""

from __future__ import annotations

import logging
import os
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

CONUBE_GRAFANA_DASHBOARD_URL = os.getenv(
    "CONUBE_GRAFANA_DASHBOARD_URL",
    "https://grafana.rpa4all.com/d/conube-operational/conube-operational-monitor",
)
CONUBE_TELEGRAM_NOTIFY = os.getenv("CONUBE_TELEGRAM_NOTIFY", "1").lower() not in {
    "0",
    "false",
    "off",
    "no",
}

from specialized_agents.conube_operational import (
    _count_by_responsible,
    _dedupe_pending_items,
    _filter_items_for_open_periods,
    _normalize_last_periods,
    _normalize_pending_docs,
    _open_period_keys,
    fetch_operational_snapshot,
)


def _period_key_from_date(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.year, parsed.month


def _format_period_label(period_end: str | None) -> str:
    key = _period_key_from_date(period_end)
    if not key:
        return period_end or "periodo-desconhecido"
    year, month = key
    return f"{year:04d}-{month:02d}"


def _period_key_from_blocker(item: dict[str, Any]) -> tuple[int, int] | None:
    month_value = str(item.get("mes") or "").strip().lower()
    year_value = item.get("ano")
    month_map = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }
    month = month_map.get(month_value)
    try:
        year = int(year_value)
    except (TypeError, ValueError):
        return None
    if not month:
        return None
    return year, month


def _previous_period_end(period_end: str) -> str | None:
    key = _period_key_from_date(period_end)
    if not key:
        return None
    year, month = key
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59.999Z"


def _sorted_open_periods(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        key = _period_key_from_date(item.get("period_end"))
        if key:
            return key[0], key[1], ""
        return (9999, 12, str(item.get("period_end") or ""))

    open_periods = [item for item in periods if str(item.get("status") or "").lower() == "aberto"]
    open_periods.sort(key=sort_key)
    return open_periods


def _expand_with_historical_open_periods(agent: Any, periods: list[dict[str, Any]], max_months: int = 12) -> list[dict[str, Any]]:
    open_periods = _sorted_open_periods(periods)
    if not open_periods:
        return open_periods

    earliest = open_periods[0].get("period_end")
    current = earliest if isinstance(earliest, str) else None
    known_keys = {_period_key_from_date(item.get("period_end")) for item in open_periods}
    extra: list[dict[str, Any]] = []
    consecutive_closed = 0

    for _ in range(max_months):
        current = _previous_period_end(current or "")
        if not current:
            break
        status = agent.get_period_status(current)
        item = {
            "id": status.get("_id"),
            "status": status.get("Status"),
            "period_end": current,
        }
        key = _period_key_from_date(current)
        if key in known_keys:
            continue
        known_keys.add(key)
        if str(status.get("Status") or "").lower() == "aberto":
            extra.append(item)
            consecutive_closed = 0
        else:
            consecutive_closed += 1
            if consecutive_closed >= 2:
                break

    return _sorted_open_periods(open_periods + extra)


def _task_conclude_params(task: dict[str, Any]) -> str:
    has_attachments = bool(task.get("_anexos"))
    year = task.get("anoCompetencia") or ""
    month = task.get("mesCompetencia") or ""
    params = {
        "sem-anexo-cliente": "false" if has_attachments else "true",
        "assunto": task.get("Assunto") or task.get("assunto") or task.get("nome") or "",
        "ano-inicio": year,
        "mes-inicio": month,
        "ano-fim": year,
        "mes-fim": month,
        "vencimento": task.get("Vencimento") or task.get("vencimento") or "",
        "valor": task.get("valor") or 0,
    }
    return urlencode(params)


def operational_summary_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return dict(snapshot.get("summary") or {})


def fetch_operational_summary(agent: Any, *, months_back: int = 12) -> dict[str, Any]:
    snapshot = fetch_operational_snapshot(agent, months_back=months_back)
    return operational_summary_from_snapshot(snapshot)


def _metric_line(label: str, before: dict[str, Any], after: dict[str, Any], key: str) -> str:
    return f"{label}: {int(before.get(key) or 0)} → {int(after.get(key) or 0)}"


def _action_summary_lines(actions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in actions:
        name = str(item.get("action") or "acao")
        processed = item.get("processed")
        blocked = item.get("blocked")
        status = item.get("status")
        detail = f"• {name}"
        if processed is not None:
            detail += f" — processados: {processed}"
        if blocked is not None:
            detail += f", bloqueados: {blocked}"
        if status:
            detail += f" ({status})"
        lines.append(detail)

        if name == "check-billing-boletos":
            from specialized_agents.conube_billing import format_billing_telegram_lines

            nested = item.get("result") or {}
            lines.extend(f"  {line}" for line in format_billing_telegram_lines(nested))
            intent = item.get("payment_intent") or {}
            if intent.get("status") == "pending_approval":
                lines.append(
                    f"  ↳ pagamento via Mercado Pago aguardando aprovação (intent {intent.get('intent_id')})"
                )
            elif intent.get("status") == "error":
                lines.append(f"  ↳ intent de pagamento falhou: {intent.get('error')}")
            continue

        nested = item.get("result")
        if isinstance(nested, dict):
            for row in nested.get("results") or []:
                if not isinstance(row, dict):
                    continue
                row_status = str(row.get("status") or "").lower()
                if row_status in {"blocked", "error", "unknown", "unsupported"}:
                    label = (
                        row.get("period")
                        or row.get("subject")
                        or row.get("competence")
                        or row.get("task_id")
                        or "item"
                    )
                    message = row.get("message") or ", ".join(row.get("blockers") or [])
                    lines.append(f"  ↳ {label}: {row_status}" + (f" — {message}" if message else ""))
    return lines


def format_remediation_telegram_message(result: dict[str, Any]) -> str:
    before = result.get("before") or {}
    after = result.get("after") or before
    actions = result.get("actions") or []
    status = str(result.get("status") or "unknown")
    lines = [
        "<b>Conube — remediação executada</b>",
        f"Status: <b>{status}</b>",
    ]

    if before or after:
        lines.extend(
            [
                "",
                "<b>Antes → Depois</b>",
                _metric_line("Períodos abertos", before, after, "open_periods_count"),
                _metric_line("Pendências cliente", before, after, "client_actionable_items_count"),
                _metric_line("Pendências contador", before, after, "accountant_owned_items_count"),
                _metric_line("Pendências totais", before, after, "pending_items_count"),
                _metric_line("Em atraso", before, after, "overdue_items_count"),
            ]
        )

    if actions:
        lines.extend(["", "<b>Ações</b>", *_action_summary_lines(actions)])
    elif result.get("remediation_needed") is False:
        lines.append("")
        lines.append("Nenhum apontamento acionável pelo agente.")

    lines.extend(["", f'<a href="{CONUBE_GRAFANA_DASHBOARD_URL}">Abrir painel Grafana</a>'])
    return "\n".join(lines)


def notify_remediation_result(result: dict[str, Any], *, force: bool = False) -> bool:
    if not CONUBE_TELEGRAM_NOTIFY and not force:
        return False

    actions = result.get("actions") or []
    has_changes = any(int(item.get("processed") or 0) > 0 for item in actions if isinstance(item, dict))
    should_notify = force or has_changes or str(result.get("status")) == "warning" or bool(actions)
    if not should_notify and result.get("remediation_needed") is False:
        return False

    try:
        from specialized_agents.telegram_notify import send_telegram_message

        send_telegram_message(
            format_remediation_telegram_message(result),
            parse_mode="HTML",
        )
        return True
    except Exception:
        logger.exception("Falha ao enviar resumo de remediacao Conube no Telegram")
        return False


def needs_remediation(summary: dict[str, Any]) -> bool:
    return bool(
        int(summary.get("open_periods_count") or 0) > 0
        or int(summary.get("client_actionable_items_count") or 0) > 0
        or int(summary.get("overdue_items_count") or 0) > 0
    )


def remediate_client_pending_tasks(agent: Any) -> dict[str, Any]:
    login_result = agent.login()
    if not login_result.get("authenticated"):
        return {
            "status": "error",
            "processed": 0,
            "results": [],
            "remaining_client_tasks": [],
            "message": str(login_result.get("failure_reason") or "Login da Conube nao autenticou."),
        }

    tasks_payload = agent._authenticated_api_get(
        "tarefas?concluida=false&responsavel=&limit=100&sort=vencimento:asc",
        api_version="client",
    )
    tasks = tasks_payload.get("docs", []) if isinstance(tasks_payload, dict) else []
    client_tasks = [
        task
        for task in tasks
        if str(task.get("Responsavel") or task.get("responsavel") or "").strip().lower() == "cliente"
    ]

    results: list[dict[str, Any]] = []
    for task in client_tasks:
        subject = str(task.get("Assunto") or "").strip()
        task_id = str(task.get("_id") or "")
        if subject == "Informe de Rendimentos - Sócios" and task.get("_anexos"):
            response = agent.conclude_task(task)
            results.append(
                {
                    "task_id": task_id,
                    "subject": subject,
                    "action": "conclude",
                    "status": response.get("Status") or "Concluida",
                    "result": "completed",
                }
            )
            continue
        if subject == "TFE - Pagamento da Taxa Municipal" and task.get("_tarefaModelo", {}).get("possuiRecalculo"):
            response = agent.request_task_recalculation(task_id)
            results.append(
                {
                    "task_id": task_id,
                    "subject": subject,
                    "action": "request_recalculation",
                    "status": response.get("Status") or "Em análise",
                    "result": "updated",
                }
            )
            continue
        results.append(
            {
                "task_id": task_id,
                "subject": subject,
                "action": "none",
                "status": task.get("Status"),
                "result": "unsupported",
            }
        )

    remaining_payload = agent._authenticated_api_get(
        "tarefas?concluida=false&responsavel=&limit=100&sort=vencimento:asc",
        api_version="client",
    )
    remaining_tasks = remaining_payload.get("docs", []) if isinstance(remaining_payload, dict) else []
    remaining_client_tasks = [
        {
            "task_id": task.get("_id"),
            "subject": task.get("Assunto"),
            "status": task.get("Status"),
        }
        for task in remaining_tasks
        if str(task.get("Responsavel") or "").strip().lower() == "cliente"
    ]
    return {
        "status": "ok",
        "processed": len(results),
        "results": results,
        "remaining_client_tasks": remaining_client_tasks,
    }


def close_open_financial_periods(agent: Any, *, limit: int = 12) -> dict[str, Any]:
    if limit < 1:
        raise RuntimeError("O limite informado para fechamento de periodos precisa ser maior que zero.")

    login_result = agent.login()
    if not login_result.get("authenticated"):
        return {
            "status": "error",
            "processed": 0,
            "blocked": 0,
            "results": [],
            "message": str(login_result.get("failure_reason") or "Login da Conube nao autenticou."),
        }

    raw_periods = agent._authenticated_api_get("transactions/last-periods", api_version="client/v2")
    periods = _normalize_last_periods(raw_periods if isinstance(raw_periods, list) else [])
    open_periods = _expand_with_historical_open_periods(agent, periods)

    results: list[dict[str, Any]] = []
    for period in open_periods[:limit]:
        period_end = str(period.get("period_end") or "").strip()
        if not period_end:
            results.append(
                {
                    "period": _format_period_label(period_end),
                    "status": "error",
                    "message": "Periodo sem data final.",
                }
            )
            continue

        status_before = agent.get_period_status(period_end)
        period_id = str(status_before.get("_id") or period.get("id") or "").strip()
        blocker_labels: list[str] = []
        if not period_id:
            results.append(
                {
                    "period": _format_period_label(period_end),
                    "status": "error",
                    "message": "Periodo sem identificador resolvido pelo checkPeriodo.",
                }
            )
            continue
        if str(status_before.get("Status") or "").lower() == "fechado":
            results.append(
                {
                    "period": _format_period_label(period_end),
                    "period_id": period_id,
                    "status": "already_closed",
                    "blockers": blocker_labels,
                }
            )
            continue

        preview = agent.get_period_close_preview(period_id)
        blockers = preview if isinstance(preview, list) else preview.get("message") if isinstance(preview, dict) else []
        blockers = blockers if isinstance(blockers, list) else []
        current_key = _period_key_from_date(period_end)
        blocker_labels = [
            f"{item.get('mes')} - {item.get('ano')}"
            for item in blockers
            if isinstance(item, dict) and item.get("mes") and item.get("ano")
        ]
        blocker_keys = {
            key
            for item in blockers
            if isinstance(item, dict)
            for key in [_period_key_from_blocker(item)]
            if key
        }
        has_external_blockers = bool(current_key and any(key != current_key for key in blocker_keys))
        if has_external_blockers:
            results.append(
                {
                    "period": _format_period_label(period_end),
                    "period_id": period_id,
                    "status": "blocked",
                    "blockers": blocker_labels,
                }
            )
            continue

        close_response = agent.close_period(period_id)
        status_after = agent.get_period_status(period_end)
        final_status = str(status_after.get("Status") or "")
        results.append(
            {
                "period": _format_period_label(period_end),
                "period_id": period_id,
                "status": "closed" if final_status.lower() == "fechado" else "unknown",
                "status_before": status_before.get("Status"),
                "status_after": final_status,
                "blockers": blocker_labels,
                "close_response": close_response,
            }
        )

    processed = len([item for item in results if item.get("status") == "closed"])
    blocked = len([item for item in results if item.get("status") == "blocked"])
    return {
        "status": "ok" if processed or not blocked else "warning",
        "processed": processed,
        "blocked": blocked,
        "results": results,
    }


def check_billing_boletos(agent: Any, *, declare_payment_intent: bool = True) -> dict[str, Any] | None:
    """Detecta boletos pendentes (faturas Vindi) e declara intent de pagamento via Mercado Pago.

    Retorna a ação para o relatório de remediação, ou None quando não há
    cobrança pendente. O pagamento em si só acontece após aprovação Telegram
    do intent conube_pay_billing_boleto_scheduled (risk=high).
    """
    from specialized_agents.conube_billing import fetch_pending_billing, format_brl

    billing = fetch_pending_billing(agent, with_payment_data=True)
    if billing.get("status") != "ok":
        return {
            "action": "check-billing-boletos",
            "status": "error",
            "processed": 0,
            "result": billing,
        }
    pending_count = int(billing.get("pending_count") or 0)
    if pending_count == 0:
        return None

    action: dict[str, Any] = {
        "action": "check-billing-boletos",
        "status": "detected",
        "processed": 0,
        "pending": pending_count,
        "result": billing,
    }
    if declare_payment_intent:
        try:
            from specialized_agents.conube_agent_langgraph import ConubeScheduledBillingPaymentAgent

            payment_agent = ConubeScheduledBillingPaymentAgent()
            try:
                state = payment_agent.run(
                    target="conube_billing_boleto",
                    extra={
                        "pending_count": pending_count,
                        "total_amount_brl": format_brl(int(billing.get("total_amount_cents") or 0)),
                        "dry_run": False,
                        "limit": pending_count,
                    },
                )
            finally:
                payment_agent.close()
            if state.get("approval") == "pending":
                action["payment_intent"] = {
                    "status": "pending_approval",
                    "intent_id": state.get("intent_id"),
                    "thread_id": state.get("thread_id"),
                }
            else:
                action["payment_intent"] = {
                    "status": state.get("status"),
                    "outcome": state.get("outcome"),
                }
                paid = int(((state.get("_result") or {}).get("processed")) or 0)
                action["processed"] = paid
        except Exception as exc:
            logger.exception("Falha ao declarar intent de pagamento do boleto Conube")
            action["payment_intent"] = {"status": "error", "error": str(exc)}
    return action


def run_remediation(
    agent: Any,
    *,
    close_periods_limit: int = 12,
    run_client_tasks: bool = True,
    run_selenium_balances: bool = True,
    run_selenium_tasks: bool = True,
    selenium_balances_limit: int = 12,
    selenium_tasks_limit: int = 20,
    months_back: int = 12,
    run_billing_check: bool = True,
) -> dict[str, Any]:
    from specialized_agents.conube_selenium import (
        close_overdue_balances_without_movement,
        remediate_pending_tasks_selenium,
    )

    before = fetch_operational_summary(agent, months_back=months_back)
    actions: list[dict[str, Any]] = []

    if int(before.get("open_periods_count") or 0) > 0:
        close_result = close_open_financial_periods(agent, limit=close_periods_limit)
        actions.append(
            {
                "action": "close-open-financial-periods",
                "status": close_result.get("status"),
                "processed": close_result.get("processed", 0),
                "blocked": close_result.get("blocked", 0),
                "result": close_result,
            }
        )

    if run_client_tasks and int(before.get("client_actionable_items_count") or 0) > 0:
        tasks_result = remediate_client_pending_tasks(agent)
        actions.append(
            {
                "action": "remediate-client-pending-tasks",
                "status": tasks_result.get("status"),
                "processed": tasks_result.get("processed", 0),
                "remaining": len(tasks_result.get("remaining_client_tasks", [])),
                "result": tasks_result,
            }
        )

    if run_selenium_balances and int(before.get("overdue_items_count") or 0) > 0:
        balances_result = close_overdue_balances_without_movement(agent, limit=selenium_balances_limit)
        actions.append(
            {
                "action": "close-overdue-balances-selenium",
                "status": balances_result.get("status"),
                "processed": balances_result.get("processed", 0),
                "result": balances_result,
            }
        )

    if run_selenium_tasks and int(before.get("overdue_items_count") or 0) > 0:
        selenium_tasks_result = remediate_pending_tasks_selenium(agent, limit=selenium_tasks_limit)
        actions.append(
            {
                "action": "remediate-pending-tasks-selenium",
                "status": selenium_tasks_result.get("status"),
                "processed": selenium_tasks_result.get("processed", 0),
                "result": selenium_tasks_result,
            }
        )

    if run_billing_check:
        try:
            billing_action = check_billing_boletos(agent)
        except Exception as exc:
            logger.exception("Falha na checagem de boletos da Conube")
            billing_action = {
                "action": "check-billing-boletos",
                "status": "error",
                "processed": 0,
                "result": {"message": str(exc)},
            }
        if billing_action is not None:
            actions.append(billing_action)

    after = fetch_operational_summary(agent, months_back=months_back)
    status = "ok"
    if (
        int(after.get("open_periods_count") or 0) > 0
        or int(after.get("client_actionable_items_count") or 0) > 0
        or int(after.get("overdue_items_count") or 0) > 0
    ):
        status = "warning"
    payload = {
        "status": status,
        "actions": actions,
        "before": before,
        "after": after,
        "remediation_needed": needs_remediation(before),
    }
    payload["telegram_notification_sent"] = notify_remediation_result(payload)
    return payload