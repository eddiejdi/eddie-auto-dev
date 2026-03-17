#!/usr/bin/env python3
"""Exportador Prometheus para auditoria operacional da Conube."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("conube_exporter")

EXPORTER_PORT = int(os.getenv("CONUBE_EXPORTER_PORT", "9662"))
CONUBE_EXPORTER_CACHE_SECONDS = int(os.getenv("CONUBE_EXPORTER_CACHE_SECONDS", "300"))
CONUBE_EXPORTER_HEADLESS = os.getenv("CONUBE_EXPORTER_HEADLESS", "1").lower() not in {"0", "false", "off", "no"}
CONUBE_EXPORTER_MONTHS_BACK = int(os.getenv("CONUBE_EXPORTER_MONTHS_BACK", "12"))
ConubePortalAgent = None
load_conube_credentials = None


def _ensure_conube_dependencies() -> tuple[Any, Any]:
    global ConubePortalAgent, load_conube_credentials
    if ConubePortalAgent is None or load_conube_credentials is None:
        from specialized_agents.conube_agent import ConubePortalAgent as _ConubePortalAgent
        from specialized_agents.conube_agent import load_conube_credentials as _load_conube_credentials

        ConubePortalAgent = _ConubePortalAgent
        load_conube_credentials = _load_conube_credentials
    return ConubePortalAgent, load_conube_credentials


class ConubeMetricsCollector:
    """Coleta e expõe métricas da Conube com cache curto."""

    def __init__(self, cache_seconds: int = CONUBE_EXPORTER_CACHE_SECONDS) -> None:
        self.cache_seconds = cache_seconds
        self._cached_payload = ""
        self._cached_until = 0.0
        self._refresh_in_progress = False
        self._lock = threading.Lock()

    def _metric(
        self,
        lines: list[str],
        name: str,
        value: float | int,
        help_text: str = "",
        metric_type: str = "gauge",
        labels: str = "",
    ) -> None:
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {metric_type}")
        lines.append(f"{name}{labels} {value}")

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _fetch_snapshot(self) -> dict[str, Any]:
        conube_agent_cls, load_credentials = _ensure_conube_dependencies()
        email, password = load_credentials()
        with conube_agent_cls(email, password, headless=CONUBE_EXPORTER_HEADLESS) as agent:
            summary, audit, billing = self._fetch_snapshot_via_api(agent)
        return {"summary": summary, "audit": audit, "billing": billing}

    def _fetch_snapshot_via_api(self, agent: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        agent.login()

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

        periods = agent._normalize_last_periods(api_checks.get("transactions_last_periods", []))
        audited = []
        for item in periods[:CONUBE_EXPORTER_MONTHS_BACK]:
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
                pending_items.extend(agent._normalize_pending_docs(payload["docs"], key))

        pending_items = agent._dedupe_pending_items(pending_items)
        open_period_keys = agent._open_period_keys(audited)
        overdue_items = [
            item
            for item in pending_items
            if str(item.get("status") or "").lower() in {"pendente", "atrasado", "aberto"}
        ]
        overdue_items.sort(key=lambda item: item.get("due_date") or "")
        relevant_items = agent._filter_items_for_open_periods(overdue_items, open_period_keys)
        certificate = agent._summarize_certificate(api_checks.get("certificados", []))
        open_periods = [item for item in audited if str(item.get("status") or "").lower() == "aberto"]
        responsible_counts = agent._count_by_responsible(pending_items)

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
            "dashboard_loaded": False,
            "dashboard_error": None,
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
        return summary, audit, billing

    def _build_metrics(self, snapshot: dict[str, Any]) -> str:
        summary = snapshot.get("summary", {})
        audit = snapshot.get("audit", {})
        billing = snapshot.get("billing", {})
        lines: list[str] = []

        self._metric(lines, "conube_exporter_up", 1, "Exporter da Conube ativo")
        self._metric(lines, "conube_dashboard_loaded", 1 if summary.get("dashboard_loaded") else 0,
                     "Dashboard da Conube carregou no headless")
        self._metric(lines, "conube_open_periods_total", summary.get("open_periods_count", 0),
                     "Total de periodos financeiros abertos")
        self._metric(lines, "conube_pending_items_total", summary.get("pending_items_count", 0),
                     "Total de pendencias deduplicadas")
        self._metric(lines, "conube_overdue_items_total", summary.get("overdue_items_count", 0),
                     "Total de pendencias em atraso")
        self._metric(lines, "conube_client_actionable_items_total", summary.get("client_actionable_items_count", 0),
                     "Pendencias acionaveis pelo cliente")
        self._metric(lines, "conube_accountant_owned_items_total", summary.get("accountant_owned_items_count", 0),
                     "Pendencias sob responsabilidade do contador")
        self._metric(lines, "conube_relevant_open_period_items_total", summary.get("relevant_items_count", 0),
                     "Pendencias vinculadas aos periodos abertos")

        certificate = summary.get("certificate", {})
        self._metric(lines, "conube_certificate_present", 1 if certificate.get("present") else 0,
                     "Certificado digital presente")
        expired = certificate.get("expired")
        self._metric(lines, "conube_certificate_expired", 1 if expired else 0,
                     "Certificado digital expirado")

        self._metric(lines, "conube_financial_periods_open_total", audit.get("open_periods_count", 0),
                     "Total de periodos auditados em aberto")
        self._metric(lines, "conube_financial_periods_closed_total", audit.get("closed_periods_count", 0),
                     "Total de periodos auditados fechados")
        self._metric(lines, "conube_billing_blocked", 1 if billing.get("blocked_by_certificate") else 0,
                     "Faturamento bloqueado por certificado")

        lines.append("# HELP conube_financial_period_open Status aberto por competencia (1=aberto)")
        lines.append("# TYPE conube_financial_period_open gauge")
        lines.append("# HELP conube_financial_period_logs_count Quantidade de logs na competencia")
        lines.append("# TYPE conube_financial_period_logs_count gauge")

        for item in audit.get("periods", []):
            period = self._escape(str(item.get("period") or "unknown"))
            status = str(item.get("status") or "").lower()
            labels = f'{{period="{period}"}}'
            lines.append(f"conube_financial_period_open{labels} {1 if status == 'aberto' else 0}")
            lines.append(f"conube_financial_period_logs_count{labels} {int(item.get('logs_count', 0) or 0)}")

        lines.append("# HELP conube_pending_item_overdue Itens em atraso por assunto (1=presente)")
        lines.append("# TYPE conube_pending_item_overdue gauge")
        for item in summary.get("top_overdue_items", []):
            subject = self._escape(str(item.get("subject") or "sem-assunto")[:120])
            source = self._escape(str(item.get("source") or "unknown"))
            labels = f'{{subject="{subject}",source="{source}"}}'
            lines.append(f"conube_pending_item_overdue{labels} 1")

        return "\n".join(lines) + "\n"

    def _build_placeholder_payload(self) -> str:
        lines: list[str] = []
        self._metric(lines, "conube_exporter_up", 0, "Exporter da Conube ativo")
        self._metric(lines, "conube_exporter_refresh_in_progress", 1,
                     "Coleta em background em andamento")
        return "\n".join(lines) + "\n"

    def _refresh_cache(self) -> None:
        try:
            snapshot = self._fetch_snapshot()
            payload = self._build_metrics(snapshot)
        except Exception as exc:
            logger.exception("Falha ao coletar metricas da Conube")
            payload = (
                "# HELP conube_exporter_up Exporter da Conube ativo\n"
                "# TYPE conube_exporter_up gauge\n"
                "conube_exporter_up 0\n"
                f'conube_exporter_error{{message="{self._escape(str(exc)[:180])}"}} 1\n'
            )

        with self._lock:
            self._cached_payload = payload
            self._cached_until = time.time() + self.cache_seconds
            self._refresh_in_progress = False

    def _trigger_refresh(self) -> None:
        with self._lock:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True
        threading.Thread(target=self._refresh_cache, name="conube-exporter-refresh", daemon=True).start()

    def collect(self) -> str:
        now = time.time()
        with self._lock:
            cached_payload = self._cached_payload
            cached_until = self._cached_until
            refresh_in_progress = self._refresh_in_progress

        if cached_payload and now < cached_until:
            return cached_payload

        if not refresh_in_progress:
            self._trigger_refresh()

        return cached_payload or self._build_placeholder_payload()


class MetricsHandler(BaseHTTPRequestHandler):
    collector = ConubeMetricsCollector()

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/metrics", "/"}:
            self.send_response(404)
            self.end_headers()
            return
        payload = self.collector.collect().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = ThreadingHTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    MetricsHandler.collector._trigger_refresh()
    logger.info("Conube exporter listening on :%s", EXPORTER_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
