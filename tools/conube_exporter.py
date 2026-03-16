#!/usr/bin/env python3
"""Exportador Prometheus para auditoria operacional da Conube."""

from __future__ import annotations

import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from specialized_agents.conube_agent import ConubePortalAgent, load_conube_credentials

logger = logging.getLogger("conube_exporter")

EXPORTER_PORT = int(os.getenv("CONUBE_EXPORTER_PORT", "9662"))
CONUBE_EXPORTER_CACHE_SECONDS = int(os.getenv("CONUBE_EXPORTER_CACHE_SECONDS", "300"))
CONUBE_EXPORTER_HEADLESS = os.getenv("CONUBE_EXPORTER_HEADLESS", "1").lower() not in {"0", "false", "off", "no"}
CONUBE_EXPORTER_MONTHS_BACK = int(os.getenv("CONUBE_EXPORTER_MONTHS_BACK", "12"))


class ConubeMetricsCollector:
    """Coleta e expõe métricas da Conube com cache curto."""

    def __init__(self, cache_seconds: int = CONUBE_EXPORTER_CACHE_SECONDS) -> None:
        self.cache_seconds = cache_seconds
        self._cached_payload = ""
        self._cached_until = 0.0

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
        email, password = load_conube_credentials()
        with ConubePortalAgent(email, password, headless=CONUBE_EXPORTER_HEADLESS) as agent:
            summary = agent.operational_summary()
            audit = agent.financial_periods_audit(months_back=CONUBE_EXPORTER_MONTHS_BACK)
            billing = agent.billing_diagnostic()
        return {"summary": summary, "audit": audit, "billing": billing}

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

    def collect(self) -> str:
        now = time.time()
        if self._cached_payload and now < self._cached_until:
            return self._cached_payload

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

        self._cached_payload = payload
        self._cached_until = now + self.cache_seconds
        return payload


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
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    logger.info("Conube exporter listening on :%s", EXPORTER_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
