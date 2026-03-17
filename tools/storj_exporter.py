#!/usr/bin/env python3
"""Exportador de métricas do Storj Storage Node para Prometheus/Grafana.

Coleta métricas da API REST local do Storj node (porta 14002)
e expõe em formato Prometheus exposition na porta 9651.
"""
from __future__ import annotations

import json
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger("storj_exporter")

STORJ_API_BASE = "http://localhost:14002/api"
EXPORTER_PORT = 9651


class StorjMetrics:
    """Coleta métricas do Storj Storage Node via API local."""

    def __init__(self, base_url: str = STORJ_API_BASE) -> None:
        """Inicializa o coletor de métricas.

        Args:
            base_url: URL base da API do Storj node.
        """
        self.base_url = base_url.rstrip("/")

    def _get(self, endpoint: str) -> dict[str, Any] | None:
        """Faz GET na API do Storj node.

        Args:
            endpoint: Caminho do endpoint (ex: 'sno/').

        Returns:
            Dict com JSON da resposta ou None em caso de erro.
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, json.JSONDecodeError, OSError) as e:
            logger.warning(f"Erro ao acessar Storj API {endpoint}: {e}")
            return None

    def _metric(
        self,
        lines: list[str],
        name: str,
        value: float | int,
        help_text: str = "",
        metric_type: str = "gauge",
        labels: str = "",
    ) -> None:
        """Adiciona uma métrica Prometheus às linhas.

        Args:
            lines: Lista de linhas para append.
            name: Nome da métrica.
            value: Valor numérico.
            help_text: Texto de ajuda HELP.
            metric_type: Tipo (gauge, counter, etc.).
            labels: Labels formatadas ex: '{foo="bar"}'.
        """
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {metric_type}")
        lines.append(f"{name}{labels} {value}")

    def collect(self) -> str:
        """Coleta todas as métricas e retorna em formato Prometheus.

        Returns:
            String com métricas no formato Prometheus exposition.
        """
        lines: list[str] = []

        # --- SNO dashboard ---
        sno = self._get("sno/")
        satellites_stats = self._get("sno/satellites")
        if sno:
            # Node online
            is_online = 1 if sno.get("nodeID") else 0
            self._metric(lines, "storj_node_online", is_online,
                         "Node está online (1=sim, 0=não)")

            # Disk space
            disk = sno.get("diskSpace", {})
            self._metric(lines, "storj_disk_used_bytes",
                         disk.get("used", 0),
                         "Espaço em disco usado pelo node")
            self._metric(lines, "storj_disk_available_bytes",
                         disk.get("available", 0),
                         "Espaço alocado total")
            self._metric(lines, "storj_disk_trash_bytes",
                         disk.get("trash", 0),
                         "Espaço usado pelo trash")
            self._metric(lines, "storj_disk_overused_bytes",
                         disk.get("overused", 0),
                         "Espaço excedente")

            # Utilização percentual
            available = disk.get("available", 1) or 1
            used = disk.get("used", 0)
            pct = round((used / available) * 100, 2)
            self._metric(lines, "storj_disk_usage_percent", pct,
                         "Percentual de uso do disco alocado")

            # Bandwidth
            bw = sno.get("bandwidth", {})
            self._metric(lines, "storj_bandwidth_used_bytes",
                         bw.get("used", 0),
                         "Bandwidth total usado")

            # Version
            version = sno.get("version", "0.0.0")
            up_to_date = 1 if sno.get("upToDate") else 0
            self._metric(lines, "storj_version_up_to_date", up_to_date,
                         "Versão está atualizada (1=sim)")

            # QUIC
            quic_ok = 1 if sno.get("quicStatus") == "OK" else 0
            self._metric(lines, "storj_quic_ok", quic_ok,
                         "QUIC está funcionando (1=sim)")

            # Satellites
            satellites = sno.get("satellites") or []
            self._metric(lines, "storj_satellites_count",
                         len(satellites),
                         "Número de satélites conectados")

            # Scores por satélite
            lines.append("# HELP storj_audit_score Score de auditoria (0-1)")
            lines.append("# TYPE storj_audit_score gauge")
            lines.append("# HELP storj_suspension_score Score de suspensão (0-1)")
            lines.append("# TYPE storj_suspension_score gauge")
            lines.append("# HELP storj_online_score Score de uptime (0-1)")
            lines.append("# TYPE storj_online_score gauge")
            lines.append("# HELP storj_satellite_vetted Satélite já concluiu vetting (1=sim)")
            lines.append("# TYPE storj_satellite_vetted gauge")
            lines.append("# HELP storj_satellite_disqualified Satélite desqualificou o node (1=sim)")
            lines.append("# TYPE storj_satellite_disqualified gauge")
            lines.append("# HELP storj_satellite_suspended Satélite suspendeu o node (1=sim)")
            lines.append("# TYPE storj_satellite_suspended gauge")

            audits_by_url: dict[str, dict[str, Any]] = {}
            if satellites_stats:
                for audit in satellites_stats.get("audits", []):
                    name = audit.get("satelliteName", "unknown")
                    audits_by_url[name.split(":")[0]] = audit

            for sat in satellites:
                sid = sat.get("id", "unknown")[:16]
                url = sat.get("url", "unknown").split(":")[0]
                lbl = f'{{satellite_id="{sid}",url="{url}"}}'
                audit = audits_by_url.get(url, {})
                lines.append(
                    f'storj_audit_score{lbl} {audit.get("auditScore", sat.get("auditScore", 0))}'
                )
                lines.append(
                    f'storj_suspension_score{lbl} {audit.get("suspensionScore", sat.get("suspensionScore", 0))}'
                )
                lines.append(
                    f'storj_online_score{lbl} {audit.get("onlineScore", sat.get("onlineScore", 0))}'
                )
                lines.append(
                    f'storj_satellite_vetted{lbl} {1 if sat.get("vettedAt") else 0}'
                )
                lines.append(
                    f'storj_satellite_disqualified{lbl} {1 if sat.get("disqualified") else 0}'
                )
                lines.append(
                    f'storj_satellite_suspended{lbl} {1 if sat.get("suspended") else 0}'
                )

        # --- Estimated payout ---
        payout = self._get("sno/estimated-payout")
        if payout:
            current = payout.get("currentMonth", {})
            egress_pay = current.get("egressBandwidthPayout", 0)
            disk_pay = current.get("diskSpacePayout", 0)
            held = current.get("held", 0)
            net_payout = current.get("payout", 0)
            month_estimate = payout.get("currentMonthExpectations", 0)
            self._metric(lines, "storj_payout_current_month_cents",
                         egress_pay + disk_pay,
                         "Ganhos brutos mês atual (centavos USD)")
            self._metric(lines, "storj_payout_net_payout_cents",
                         net_payout,
                         "Payout líquido confirmado mês atual (após held)")
            self._metric(lines, "storj_payout_month_estimate_cents",
                         month_estimate,
                         "Estimativa projetada para o mês inteiro")
            self._metric(lines, "storj_payout_current_egress_cents",
                         egress_pay,
                         "Ganhos egress mês atual (centavos USD)")
            self._metric(lines, "storj_payout_current_storage_cents",
                         disk_pay,
                         "Ganhos storage mês atual (centavos USD)")
            self._metric(lines, "storj_payout_current_held_cents",
                         held,
                         "Valor retido (held) mês atual (centavos USD)")

            previous = payout.get("previousMonth", {})
            prev_total = (
                previous.get("egressBandwidthPayout", 0)
                + previous.get("diskSpacePayout", 0)
            )
            self._metric(lines, "storj_payout_previous_month_cents",
                         prev_total,
                         "Ganhos mês anterior (centavos USD)")

        # --- ETH wallet balance (zkSync Era — rede de pagamento Storj) ---
        try:
            wallet = None
            if sno:
                wallet = sno.get("wallet")
            if wallet:
                wallet_url = (
                    "https://block-explorer-api.mainnet.zksync.io/api"
                    f"?module=account&action=balance&address={wallet}"
                )
                req = Request(
                    wallet_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "storj-exporter/1.0",
                    },
                )
                with urlopen(req, timeout=10) as resp:
                    wdata = json.loads(resp.read().decode("utf-8"))
                if wdata.get("status") == "1":
                    balance_wei = int(wdata.get("result", "0") or "0")
                    balance_eth = balance_wei / 1e18
                    self._metric(
                        lines,
                        "storj_wallet_eth_balance",
                        balance_eth,
                        "Saldo ETH da carteira do node (zkSync Era)",
                    )
        except (URLError, json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning(f"Erro ao consultar saldo ETH: {e}")

        # --- Exporter up ---
        self._metric(lines, "storj_exporter_up", 1,
                     "Exporter está funcionando")

        return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """Handler HTTP para servir métricas Prometheus."""

    collector = StorjMetrics()

    def do_GET(self) -> None:
        """Responde GET /metrics com métricas Prometheus."""
        if self.path in ("/metrics", "/"):
            metrics = self.collector.collect()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suprime logs de request para não poluir output."""


def main() -> None:
    """Inicia o servidor HTTP do exporter."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    logger.info(f"Storj exporter rodando em http://0.0.0.0:{EXPORTER_PORT}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Exporter encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()
