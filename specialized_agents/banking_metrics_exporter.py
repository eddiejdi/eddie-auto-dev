"""
Banking Agent — Exportador de métricas Prometheus.

Expõe métricas de:
  - Saldos por banco (gauge)
  - Volume de transações (counter)
  - Latência de API por conector (histogram)
  - Status de autenticação (gauge/info)
  - Alertas de gastos (gauge)
  - Categorização de despesas (gauge)
  - PIX enviados/recebidos (counter)
  - Erros de conexão (counter)

Porta: 9102 (standalone) ou via /metrics/banking no FastAPI 8503.
"""
import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
)

logger = logging.getLogger("eddie.banking.metrics")


class BankingMetricsExporter:
    """Exportador de métricas Prometheus para o Banking Agent."""

    _banking_metrics: Optional["BankingMetricsExporter"] = None

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()

        self.balance_available = Gauge(
            "banking_balance_available_brl", "Saldo disponível em reais",
            ["provider", "account_id"], registry=self.registry,
        )
        self.balance_blocked = Gauge(
            "banking_balance_blocked_brl", "Saldo bloqueado em reais",
            ["provider", "account_id"], registry=self.registry,
        )
        self.balance_total_consolidated = Gauge(
            "banking_balance_total_consolidated_brl", "Saldo total consolidado de todos os bancos",
            registry=self.registry,
        )
        self.credit_limit_available = Gauge(
            "banking_credit_limit_available_brl", "Limite de crédito disponível",
            ["provider", "card_id"], registry=self.registry,
        )
        self.credit_limit_total = Gauge(
            "banking_credit_limit_total_brl", "Limite de crédito total",
            ["provider", "card_id"], registry=self.registry,
        )
        self.transactions_total = Counter(
            "banking_transactions_total", "Total de transações processadas",
            ["provider", "tx_type", "direction"], registry=self.registry,
        )
        self.transactions_amount = Counter(
            "banking_transactions_amount_brl_total", "Soma dos valores de transações em reais",
            ["provider", "direction"], registry=self.registry,
        )
        self.spending_by_category = Gauge(
            "banking_spending_by_category_brl", "Gastos por categoria no mês atual",
            ["category"], registry=self.registry,
        )
        self.pix_sent_total = Counter(
            "banking_pix_sent_total", "Total de PIX enviados",
            ["provider"], registry=self.registry,
        )
        self.pix_received_total = Counter(
            "banking_pix_received_total", "Total de PIX recebidos",
            ["provider"], registry=self.registry,
        )
        self.pix_sent_amount = Counter(
            "banking_pix_sent_amount_brl_total", "Valor total de PIX enviados em reais",
            ["provider"], registry=self.registry,
        )
        self.pix_received_amount = Counter(
            "banking_pix_received_amount_brl_total", "Valor total de PIX recebidos em reais",
            ["provider"], registry=self.registry,
        )
        self.api_request_duration = Histogram(
            "banking_api_request_duration_seconds", "Tempo de resposta das APIs bancárias",
            ["provider", "operation"], registry=self.registry,
        )
        self.api_requests_total = Counter(
            "banking_api_requests_total", "Total de requests às APIs bancárias",
            ["provider", "operation", "status"], registry=self.registry,
        )
        self.auth_status = Gauge(
            "banking_auth_status", "Status de autenticação (1=OK, 0=Falha)",
            ["provider"], registry=self.registry,
        )
        self.auth_token_expiry = Gauge(
            "banking_auth_token_expiry_seconds", "Segundos restantes até expiração do token",
            ["provider"], registry=self.registry,
        )
        self.auth_failures_total = Counter(
            "banking_auth_failures_total", "Total de falhas de autenticação",
            ["provider", "reason"], registry=self.registry,
        )
        self.spending_alerts_active = Gauge(
            "banking_spending_alerts_active", "Número de alertas de gastos ativos",
            ["severity"], registry=self.registry,
        )
        self.statement_transaction_count = Gauge(
            "banking_statement_transaction_count", "Número de transações nos últimos 7 dias",
            registry=self.registry,
        )
        self.statement_credits = Gauge(
            "banking_statement_credits_brl", "Total de créditos (R$) nos últimos 7 dias",
            registry=self.registry,
        )
        self.statement_debits = Gauge(
            "banking_statement_debits_brl", "Total de débitos (R$) nos últimos 7 dias",
            registry=self.registry,
        )
        self.statement_net = Gauge(
            "banking_statement_net_brl", "Resultado líquido (R$) nos últimos 7 dias",
            registry=self.registry,
        )
        self.spending_threshold = Gauge(
            "banking_spending_threshold_brl", "Limite de gasto configurado por categoria",
            ["category"], registry=self.registry,
        )
        self.spending_current = Gauge(
            "banking_spending_current_brl", "Gasto atual no mês por categoria",
            ["category"], registry=self.registry,
        )
        self.spending_ratio = Gauge(
            "banking_spending_ratio", "Razão gasto/limite (>1 = acima do limite)",
            ["category"], registry=self.registry,
        )
        self.connectors_active = Gauge(
            "banking_connectors_active", "Número de conectores bancários ativos",
            registry=self.registry,
        )
        self.connector_status = Gauge(
            "banking_connector_status", "Status de conectores (1=conectado)",
            ["provider"], registry=self.registry,
        )
        self.connection_errors_total = Counter(
            "banking_connection_errors_total", "Erros de conexão por provedor",
            ["provider", "error_type"], registry=self.registry,
        )
        self.accounts_count = Gauge(
            "banking_accounts_count", "Número de contas por provedor",
            ["provider"], registry=self.registry,
        )
        self.cards_count = Gauge(
            "banking_cards_count", "Número de cartões por provedor",
            ["provider"], registry=self.registry,
        )

    def record_balance(self, provider: str, account_id: str, available: float, blocked: float) -> None:
        """Registra saldo de uma conta."""
        self.balance_available.labels(provider=provider, account_id=account_id).set(available)
        self.balance_blocked.labels(provider=provider, account_id=account_id).set(blocked)

    def record_consolidated_balance(self, total: float) -> None:
        """Registra saldo total consolidado."""
        self.balance_total_consolidated.set(total)

    def record_credit_limit(self, provider: str, card_id: str, available: float, total: float) -> None:
        """Registra limites de crédito."""
        self.credit_limit_available.labels(provider=provider, card_id=card_id).set(available)
        self.credit_limit_total.labels(provider=provider, card_id=card_id).set(total)

    def record_transaction(self, provider: str, tx_type: str, direction: str, amount: float) -> None:
        """Registra uma transação."""
        self.transactions_total.labels(provider=provider, tx_type=tx_type, direction=direction).inc()
        self.transactions_amount.labels(provider=provider, direction=direction).inc(amount)

    def record_category_spending(self, category: str, amount: float) -> None:
        """Registra gasto por categoria."""
        self.spending_by_category.labels(category=category).set(amount)

    def record_pix(self, provider: str, direction: str, amount: float) -> None:
        """Registra PIX enviado ou recebido."""
        if direction == "sent":
            self.pix_sent_total.labels(provider=provider).inc()
            self.pix_sent_amount.labels(provider=provider).inc(amount)
        else:
            self.pix_received_total.labels(provider=provider).inc()
            self.pix_received_amount.labels(provider=provider).inc(amount)

    def record_api_request(self, provider: str, operation: str, duration: float, success: bool, status: str = "") -> None:
        """Registra request a uma API bancária."""
        self.api_request_duration.labels(provider=provider, operation=operation).observe(duration)
        label = "success" if success else "error"
        self.api_requests_total.labels(provider=provider, operation=operation, status=label).inc()

    def record_auth_status(self, provider: str, authenticated: bool, token_expiry_seconds: float = 0) -> None:
        """Registra status de autenticação."""
        self.auth_status.labels(provider=provider).set(1 if authenticated else 0)
        self.auth_token_expiry.labels(provider=provider).set(token_expiry_seconds)

    def record_auth_failure(self, provider: str, reason: str) -> None:
        """Registra falha de autenticação."""
        self.auth_failures_total.labels(provider=provider, reason=reason).inc()

    def record_spending_alert(self, category: str, current: float, threshold: float, severity: str, ratio: float) -> None:
        """Registra alerta de gasto."""
        self.spending_current.labels(category=category).set(current)
        self.spending_threshold.labels(category=category).set(threshold)
        self.spending_ratio.labels(category=category).set(ratio)

    def record_connector_status(self, provider: str, connected: bool) -> None:
        """Registra status de um conector."""
        self.connector_status.labels(provider=provider).set(1 if connected else 0)

    def update_connectors_count(self, count: int) -> None:
        """Atualiza número de conectores ativos."""
        self.connectors_active.set(count)

    def record_connection_error(self, provider: str, error_type: str) -> None:
        """Registra erro de conexão."""
        self.connection_errors_total.labels(provider=provider, error_type=error_type).inc()

    def record_accounts_count(self, provider: str, accounts: int, cards: int) -> None:
        """Registra contagem de contas e cartões."""
        self.accounts_count.labels(provider=provider).set(accounts)
        self.cards_count.labels(provider=provider).set(cards)

    def update_spending_alerts_count(self, warning: int, critical: int) -> None:
        """Atualiza contagem de alertas ativos."""
        self.spending_alerts_active.labels(severity="warning").set(warning)
        self.spending_alerts_active.labels(severity="critical").set(critical)

    def _initialize_zero_metrics(self, providers: list, categories: list) -> None:
        """Inicializa todas as métricas com valores zero para todos os providers.

        Garante que o Grafana encontre séries mesmo sem conectores bancários ativos.
        """
        for p in providers or ["default"]:
            self.auth_status.labels(provider=p).set(0)
            self.connector_status.labels(provider=p).set(0)
            self.auth_token_expiry.labels(provider=p).set(0)
            for error_type in ["none", "timeout", "auth", "network"]:
                self.connection_errors_total.labels(provider=p, error_type=error_type)
            for op in ["balance", "statement", "pix"]:
                for status in ["success", "error"]:
                    self.api_requests_total.labels(provider=p, operation=op, status=status)
        for cat in categories or ["default"]:
            self.spending_by_category.labels(category=cat).set(0)
            self.spending_threshold.labels(category=cat).set(0)
            self.spending_current.labels(category=cat).set(0)
            self.spending_ratio.labels(category=cat).set(0)
        for sev in ["warning", "critical"]:
            self.spending_alerts_active.labels(severity=sev).set(0)

    async def _collect_via_api(self, api_url: str, client: httpx.AsyncClient) -> bool:
        """Coleta métricas via API REST do banking agent."""
        try:
            resp = await client.get("http://127.0.0.1:8503/banking/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                initialized = data.get("initialized", False)
                connected = data.get("providers_connected", [])
                disconnected = data.get("providers_disconnected", [])
                active_count = data.get("connectors_active", 0)
                self.update_connectors_count(active_count)
                for p in connected:
                    self.record_connector_status(p, True)
                for p in disconnected:
                    self.record_connector_status(p, False)
                all_providers = connected + disconnected

                bal_resp = await client.get("http://127.0.0.1:8503/banking/balance", timeout=10)
                if bal_resp.status_code == 200:
                    bal_data = bal_resp.json()
                    total = bal_data.get("total_available", 0)
                    self.record_consolidated_balance(float(total))
                    for b in bal_data.get("balances", []):
                        p = b.get("provider", "unknown")
                        acct = b.get("account_id", "main")
                        self.record_balance(p, acct, float(b.get("available", 0)), float(b.get("blocked", 0)))
                    logger.info("Balance collection via API: %s", total)

                stmt_resp = await client.get("http://127.0.0.1:8503/banking/statement?days=7", timeout=15)
                if stmt_resp.status_code == 200:
                    stmt = stmt_resp.json()
                    self.statement_transaction_count.set(stmt.get("transaction_count", 0))
                    self.statement_credits.set(float(stmt.get("total_credits", 0)))
                    self.statement_debits.set(float(stmt.get("total_debits", 0)))
                    net = float(stmt.get("total_credits", 0)) - float(stmt.get("total_debits", 0))
                    self.statement_net.set(net)
                    for tx in stmt.get("transactions", []):
                        self.record_transaction(
                            tx.get("provider", "unknown"),
                            tx.get("tx_type", "other"),
                            tx.get("direction", "debit"),
                            float(tx.get("amount", 0)),
                        )
                return True
        except Exception as e:
            logger.warning("API collect fallback: %s", e)
            return False

    async def collect_from_agent(self) -> None:
        """
        Coleta métricas do Banking Agent — via API REST ou import direto.
        Chamado periodicamente pelo loop de coleta.
        """
        api_collected = False
        try:
            async with httpx.AsyncClient() as client:
                api_collected = await self._collect_via_api("http://127.0.0.1:8503", client)
        except Exception as e:
            logger.warning("API collect fallback: %s", e)

        if not api_collected:
            try:
                from specialized_agents.banking import get_banking_agent
                agent = get_banking_agent()
                if agent is None:
                    raise RuntimeError("Banking Agent não disponível para coleta de métricas")
            except Exception as e:
                logger.warning("Banking Agent não disponível para coleta de métricas: %s", e)

    def get_metrics(self) -> bytes:
        """Retorna métricas em formato Prometheus."""
        return generate_latest(self.registry)

    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo JSON das métricas."""
        return {"service": "eddie-banking-metrics", "version": "1.0.0"}


def get_banking_metrics() -> "BankingMetricsExporter":
    if BankingMetricsExporter._banking_metrics is None:
        BankingMetricsExporter._banking_metrics = BankingMetricsExporter()
    return BankingMetricsExporter._banking_metrics


async def banking_metrics_collection_loop(interval: int = 60) -> None:
    """Loop de coleta periódica de métricas do Banking Agent."""
    exporter = get_banking_metrics()
    logger.info("Banking metrics collection loop started (interval=%s)", interval)
    while True:
        try:
            await exporter.collect_from_agent()
        except Exception as e:
            logger.error("Banking metrics collection error: %s", e)
        await asyncio.sleep(interval)


def start_standalone_server(port: int = 9102) -> None:
    """Inicia servidor Prometheus standalone na porta 9102."""
    exporter = BankingMetricsExporter()
    loop = asyncio.new_event_loop()
    start_http_server(port, registry=exporter.registry)
    logger.info("Banking metrics exporter running on :%s/metrics", port)
    try:
        loop.run_until_complete(banking_metrics_collection_loop())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Banking metrics exporter stopped")
        loop.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("BANKING_EXPORTER_PORT", "9102"))
    start_standalone_server(port)
