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
import httpx
import logging
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any
from collections import defaultdict

from prometheus_client import (
    Counter, Gauge, Histogram, Info,
    CollectorRegistry, generate_latest, start_http_server,
)

logger = logging.getLogger("eddie.banking.metrics")


class BankingMetricsExporter:
    """Exportador de métricas Prometheus para o Banking Agent."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        if self._initialized:
            return
        self._initialized = True

        self.registry = registry or CollectorRegistry()
        self._last_collection = 0.0

        # ─── Saldos ───
        self.balance_available = Gauge(
            "banking_balance_available_brl",
            "Saldo disponível em reais",
            ["provider", "account_id"],
            registry=self.registry,
        )
        self.balance_blocked = Gauge(
            "banking_balance_blocked_brl",
            "Saldo bloqueado em reais",
            ["provider", "account_id"],
            registry=self.registry,
        )
        self.balance_total_consolidated = Gauge(
            "banking_balance_total_consolidated_brl",
            "Saldo total consolidado de todos os bancos",
            registry=self.registry,
        )
        self.credit_limit_available = Gauge(
            "banking_credit_limit_available_brl",
            "Limite de crédito disponível",
            ["provider", "card_id"],
            registry=self.registry,
        )
        self.credit_limit_total = Gauge(
            "banking_credit_limit_total_brl",
            "Limite de crédito total",
            ["provider", "card_id"],
            registry=self.registry,
        )

        # ─── Transações ───
        self.transactions_total = Counter(
            "banking_transactions_total",
            "Total de transações processadas",
            ["provider", "type", "direction"],
            registry=self.registry,
        )
        self.transactions_amount_sum = Counter(
            "banking_transactions_amount_brl_total",
            "Soma dos valores de transações em reais",
            ["provider", "direction"],
            registry=self.registry,
        )
        self.transactions_by_category = Gauge(
            "banking_spending_by_category_brl",
            "Gastos por categoria no mês atual",
            ["category"],
            registry=self.registry,
        )

        # ─── PIX ───
        self.pix_sent_total = Counter(
            "banking_pix_sent_total",
            "Total de PIX enviados",
            ["provider"],
            registry=self.registry,
        )
        self.pix_received_total = Counter(
            "banking_pix_received_total",
            "Total de PIX recebidos",
            ["provider"],
            registry=self.registry,
        )
        self.pix_sent_amount = Counter(
            "banking_pix_sent_amount_brl_total",
            "Valor total de PIX enviados em reais",
            ["provider"],
            registry=self.registry,
        )
        self.pix_received_amount = Counter(
            "banking_pix_received_amount_brl_total",
            "Valor total de PIX recebidos em reais",
            ["provider"],
            registry=self.registry,
        )

        # ─── Latência de API ───
        self.api_request_duration = Histogram(
            "banking_api_request_duration_seconds",
            "Tempo de resposta das APIs bancárias",
            ["provider", "operation"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
            registry=self.registry,
        )
        self.api_requests_total = Counter(
            "banking_api_requests_total",
            "Total de requests às APIs bancárias",
            ["provider", "operation", "status"],
            registry=self.registry,
        )

        # ─── Autenticação ───
        self.auth_status = Gauge(
            "banking_auth_status",
            "Status de autenticação (1=OK, 0=Falha)",
            ["provider"],
            registry=self.registry,
        )
        self.auth_token_expiry_seconds = Gauge(
            "banking_auth_token_expiry_seconds",
            "Segundos restantes até expiração do token",
            ["provider"],
            registry=self.registry,
        )
        self.auth_failures_total = Counter(
            "banking_auth_failures_total",
            "Total de falhas de autenticação",
            ["provider", "reason"],
            registry=self.registry,
        )

        # ─── Alertas ───
        self.spending_alerts_active = Gauge(
            "banking_spending_alerts_active",
            "Número de alertas de gastos ativos",
            ["severity"],
            registry=self.registry,
        )

        # ── Statement Gauges (dados reais dos últimos 7 dias) ──
        self.stmt_transaction_count = Gauge(
            "banking_statement_transaction_count",
            "Número de transações nos últimos 7 dias",
            ["provider"],
            registry=self.registry,
        )
        self.stmt_credits_brl = Gauge(
            "banking_statement_credits_brl",
            "Total de créditos (R$) nos últimos 7 dias",
            ["provider"],
            registry=self.registry,
        )
        self.stmt_debits_brl = Gauge(
            "banking_statement_debits_brl",
            "Total de débitos (R$) nos últimos 7 dias",
            ["provider"],
            registry=self.registry,
        )
        self.stmt_net_brl = Gauge(
            "banking_statement_net_brl",
            "Resultado líquido (R$) nos últimos 7 dias",
            ["provider"],
            registry=self.registry,
        )
        self.spending_threshold = Gauge(
            "banking_spending_threshold_brl",
            "Limite de gasto configurado por categoria",
            ["category"],
            registry=self.registry,
        )
        self.spending_current = Gauge(
            "banking_spending_current_brl",
            "Gasto atual no mês por categoria",
            ["category"],
            registry=self.registry,
        )
        self.spending_ratio = Gauge(
            "banking_spending_ratio",
            "Razão gasto/limite (>1 = acima do limite)",
            ["category"],
            registry=self.registry,
        )

        # ─── Conectores ───
        self.connectors_active = Gauge(
            "banking_connectors_active",
            "Número de conectores bancários ativos",
            registry=self.registry,
        )
        self.connector_status = Gauge(
            "banking_connector_status",
            "Status do conector (1=conectado, 0=desconectado)",
            ["provider"],
            registry=self.registry,
        )
        self.connection_errors_total = Counter(
            "banking_connection_errors_total",
            "Total de erros de conexão com APIs bancárias",
            ["provider", "error_type"],
            registry=self.registry,
        )

        # ─── Contas ───
        self.accounts_total = Gauge(
            "banking_accounts_total",
            "Total de contas bancárias monitoradas",
            ["provider"],
            registry=self.registry,
        )
        self.cards_total = Gauge(
            "banking_credit_cards_total",
            "Total de cartões de crédito",
            ["provider"],
            registry=self.registry,
        )

        # ─── Info ───
        self.agent_info = Info(
            "banking_agent",
            "Informações do Banking Agent",
            registry=self.registry,
        )
        self.agent_info.info({
            "version": "1.0.0",
            "supported_providers": "santander,itau,nubank,mercadopago",
            "protocol": "open_finance_brasil",
        })

    # ─────────── Record methods ───────────

    def record_balance(self, provider: str, account_id: str, available: float, blocked: float = 0):
        """Registra saldo de uma conta."""
        self.balance_available.labels(provider=provider, account_id=account_id).set(available)
        self.balance_blocked.labels(provider=provider, account_id=account_id).set(blocked)

    def record_consolidated_balance(self, total: float):
        """Registra saldo total consolidado."""
        self.balance_total_consolidated.set(total)

    def record_credit_limit(self, provider: str, card_id: str, available: float, total: float):
        """Registra limites de crédito."""
        self.credit_limit_available.labels(provider=provider, card_id=card_id).set(available)
        self.credit_limit_total.labels(provider=provider, card_id=card_id).set(total)

    def record_transaction(self, provider: str, tx_type: str, direction: str, amount: float):
        """Registra uma transação."""
        self.transactions_total.labels(provider=provider, type=tx_type, direction=direction).inc()
        self.transactions_amount_sum.labels(provider=provider, direction=direction).inc(amount)

    def record_category_spending(self, category: str, amount: float):
        """Registra gasto por categoria."""
        self.transactions_by_category.labels(category=category).set(amount)

    def record_pix(self, provider: str, direction: str, amount: float):
        """Registra PIX enviado ou recebido."""
        if direction == "sent":
            self.pix_sent_total.labels(provider=provider).inc()
            self.pix_sent_amount.labels(provider=provider).inc(amount)
        else:
            self.pix_received_total.labels(provider=provider).inc()
            self.pix_received_amount.labels(provider=provider).inc(amount)

    def record_api_request(self, provider: str, operation: str, duration: float, success: bool):
        """Registra request a uma API bancária."""
        self.api_request_duration.labels(provider=provider, operation=operation).observe(duration)
        status = "success" if success else "error"
        self.api_requests_total.labels(provider=provider, operation=operation, status=status).inc()

    def record_auth_status(self, provider: str, authenticated: bool, token_expiry_seconds: float = 0):
        """Registra status de autenticação."""
        self.auth_status.labels(provider=provider).set(1 if authenticated else 0)
        self.auth_token_expiry_seconds.labels(provider=provider).set(token_expiry_seconds)

    def record_auth_failure(self, provider: str, reason: str = "unknown"):
        """Registra falha de autenticação."""
        self.auth_failures_total.labels(provider=provider, reason=reason).inc()

    def record_spending_alert(self, category: str, current: float, threshold: float, severity: str):
        """Registra alerta de gasto."""
        self.spending_current.labels(category=category).set(current)
        self.spending_threshold.labels(category=category).set(threshold)
        ratio = current / threshold if threshold > 0 else 0
        self.spending_ratio.labels(category=category).set(ratio)

    def record_connector_status(self, provider: str, connected: bool):
        """Registra status de um conector."""
        self.connector_status.labels(provider=provider).set(1 if connected else 0)

    def update_connectors_count(self, count: int):
        """Atualiza número de conectores ativos."""
        self.connectors_active.set(count)

    def record_connection_error(self, provider: str, error_type: str = "connection"):
        """Registra erro de conexão."""
        self.connection_errors_total.labels(provider=provider, error_type=error_type).inc()

    def record_accounts_count(self, provider: str, accounts: int, cards: int = 0):
        """Registra contagem de contas e cartões."""
        self.accounts_total.labels(provider=provider).set(accounts)
        self.cards_total.labels(provider=provider).set(cards)

    def update_spending_alerts_count(self, warning: int = 0, critical: int = 0):
        """Atualiza contagem de alertas ativos."""
        self.spending_alerts_active.labels(severity="warning").set(warning)
        self.spending_alerts_active.labels(severity="critical").set(critical)


    def _initialize_zero_metrics(self):
        """Inicializa todas as métricas com valores zero para todos os providers.
        
        Garante que o Grafana encontre séries mesmo sem conectores bancários ativos.
        """
        providers = ["santander", "itau", "nubank", "mercadopago"]
        categories = ["alimentacao", "transporte", "moradia", "saude", "educacao",
                       "lazer", "compras", "servicos", "outros"]

        # Conectores
        self.connectors_active.set(0)
        for p in providers:
            self.connector_status.labels(provider=p).set(0)

        # Saldos por provider
        self.balance_total_consolidated.set(0)
        for p in providers:
            self.balance_available.labels(provider=p, account_id="default").set(0)
            self.balance_blocked.labels(provider=p, account_id="default").set(0)

        # Limites de crédito
        for p in providers:
            self.credit_limit_available.labels(provider=p, card_id="default").set(0)
            self.credit_limit_total.labels(provider=p, card_id="default").set(0)

        # Contas e cartões
        for p in providers:
            self.accounts_total.labels(provider=p).set(0)
            self.cards_total.labels(provider=p).set(0)

        # Autenticação
        for p in providers:
            self.auth_status.labels(provider=p).set(0)
            self.auth_token_expiry_seconds.labels(provider=p).set(0)

        # Gastos por categoria
        for cat in categories:
            self.transactions_by_category.labels(category=cat).set(0)
            self.spending_current.labels(category=cat).set(0)
            self.spending_threshold.labels(category=cat).set(0)
            self.spending_ratio.labels(category=cat).set(0)

        # Alertas
        self.spending_alerts_active.labels(severity="warning").set(0)
        self.spending_alerts_active.labels(severity="critical").set(0)

        # Counters (inicializar com inc(0) para emitir séries no Prometheus)
        for p in providers:
            self.transactions_total.labels(provider=p, type="default", direction="credit").inc(0)
            self.transactions_total.labels(provider=p, type="default", direction="debit").inc(0)
            self.transactions_amount_sum.labels(provider=p, direction="credit").inc(0)
            self.transactions_amount_sum.labels(provider=p, direction="debit").inc(0)
            self.pix_sent_total.labels(provider=p).inc(0)
            self.pix_received_total.labels(provider=p).inc(0)
            self.pix_sent_amount.labels(provider=p).inc(0)
            self.pix_received_amount.labels(provider=p).inc(0)
            self.api_requests_total.labels(provider=p, operation="default", status="success").inc(0)
            self.api_requests_total.labels(provider=p, operation="default", status="error").inc(0)
            self.auth_failures_total.labels(provider=p, reason="none").inc(0)
            self.connection_errors_total.labels(provider=p, error_type="timeout").inc(0)
            self.connection_errors_total.labels(provider=p, error_type="auth").inc(0)
            self.connection_errors_total.labels(provider=p, error_type="network").inc(0)

        # Histogram (observe 0 para criar as séries de buckets)
        for p in providers:
            self.api_request_duration.labels(provider=p, operation="default").observe(0)

        # Spending by category (Gauge já inicializado acima)
        for cat in categories:
            self.transactions_by_category.labels(category=cat).set(0)


    async def _collect_via_api(self) -> bool:
        # Sempre inicializar métricas base para Grafana encontrar séries
        self._initialize_zero_metrics()
        """Coleta status via API REST do Banking Agent (porta 8503)."""
        api_url = "http://127.0.0.1:8503/banking/status"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(api_url)
                if resp.status_code != 200:
                    return False
                data = resp.json()

            initialized = data.get("initialized", False)
            connected = data.get("providers_connected", [])
            disconnected = data.get("providers_disconnected", [])
            active_count = data.get("connectors_active", 0)

            if not initialized or active_count == 0:
                self._initialize_zero_metrics()
                # Still mark connected providers
                for p in connected:
                    self.connector_status.labels(provider=p).set(1)
                self.connectors_active.set(len(connected))
                return True

            self.connectors_active.set(active_count)
            all_providers = ["santander", "itau", "nubank", "mercadopago"]
            for p in all_providers:
                self.connector_status.labels(provider=p).set(1 if p in connected else 0)

            # Try to get balance data
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    bal_resp = await client.get("http://127.0.0.1:8503/banking/balance")
                    if bal_resp.status_code == 200:
                        bal_data = bal_resp.json()
                        total = bal_data.get("total_available", 0)
                        self.record_consolidated_balance(float(total))
                        for b in bal_data.get("balances", []):
                            self.record_balance(
                                b.get("provider", "unknown"),
                                b.get("account_id", "main"),
                                float(b.get("available", 0)),
                                float(b.get("blocked", 0)),
                            )
            except Exception as e:
                logger.debug(f"Balance collection via API: {e}")

            # Collect transaction data from statement
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    stmt_resp = await client.get("http://127.0.0.1:8503/banking/statement?days=7")
                    if stmt_resp.status_code == 200:
                        stmt_data = stmt_resp.json()
                        tx_count = stmt_data.get("transaction_count", 0)
                        total_credits = float(stmt_data.get("total_credits", 0))
                        total_debits = float(stmt_data.get("total_debits", 0))
                        
                        # Record transactions per provider from individual txs
                        provider_credits = {}
                        provider_debits = {}
                        for tx in stmt_data.get("transactions", []):
                            prov = tx.get("provider", "unknown")
                            amt = float(tx.get("amount", 0))
                            tx_type = tx.get("type", "other")
                            if tx_type in ("credit", "CREDIT"):
                                provider_credits[prov] = provider_credits.get(prov, 0) + amt
                            else:
                                provider_debits[prov] = provider_debits.get(prov, 0) + amt
                        
                        # Update auth_status and statement gauges per provider
                        providers_with_data = {}
                        for tx in stmt_data.get("transactions", []):
                            prov = tx.get("provider")
                            if not prov:
                                continue
                            if prov not in providers_with_data:
                                providers_with_data[prov] = {"count": 0, "credits": 0.0, "debits": 0.0}
                            providers_with_data[prov]["count"] += 1
                            amt = float(tx.get("amount", 0))
                            tx_type = str(tx.get("type", "")).upper()
                            if tx_type in ("CREDITO", "CREDIT", "PIX_RECEBIDO"):
                                providers_with_data[prov]["credits"] += amt
                            else:
                                providers_with_data[prov]["debits"] += amt
                        
                        for p, stats in providers_with_data.items():
                            self.auth_status.labels(provider=p).set(1)
                            self.stmt_transaction_count.labels(provider=p).set(stats["count"])
                            self.stmt_credits_brl.labels(provider=p).set(stats["credits"])
                            self.stmt_debits_brl.labels(provider=p).set(stats["debits"])
                            self.stmt_net_brl.labels(provider=p).set(stats["credits"] - stats["debits"])
                        
                        logger.info(f"Statement collected: {tx_count} txns, providers={list(providers_with_data.keys())}")
            except Exception as e:
                logger.debug(f"Statement collection via API: {e}")

            return True

        except Exception as e:
            logger.debug(f"API status check failed: {e}")
            return False


    # ─────────── Collect from agent ───────────

    async def collect_from_agent(self):
        """
        Coleta métricas do Banking Agent — via API REST ou import direto.
        Chamado periodicamente pelo loop de coleta.
        """
        # Tentar via API REST primeiro (funciona mesmo standalone)
        try:
            api_collected = await self._collect_via_api()
            if api_collected:
                return
        except Exception as e:
            logger.debug(f"API collect fallback: {e}")

        try:
            from specialized_agents.banking_agent import get_banking_agent
            agent = get_banking_agent()

            if not agent._initialized or not agent._connectors:
                self._initialize_zero_metrics()
                return

            self.update_connectors_count(len(agent._connectors))

            # Status dos conectores
            all_providers = ["santander", "itau", "nubank", "mercadopago"]
            for p in all_providers:
                from specialized_agents.banking.models import BankProvider
                connected = BankProvider(p) in agent._connectors if p in [bp.value for bp in BankProvider] else False
                self.record_connector_status(p, connected)

            # Dados consolidados
            try:
                view = await agent.get_consolidated_view()
                self.record_consolidated_balance(float(view.total_available))

                for bal in view.balances:
                    self.record_balance(
                        bal.provider.value, bal.account_id,
                        float(bal.available), float(bal.blocked),
                    )

                for card in view.credit_cards:
                    self.record_credit_limit(
                        card.provider.value, card.id,
                        float(card.available_limit), float(card.credit_limit),
                    )

                # Contar contas/cartões por provider
                accounts_by_provider: Dict[str, int] = defaultdict(int)
                cards_by_provider: Dict[str, int] = defaultdict(int)
                for acc in view.accounts:
                    accounts_by_provider[acc.provider.value] += 1
                for card in view.credit_cards:
                    cards_by_provider[card.provider.value] += 1
                for p in all_providers:
                    self.record_accounts_count(p, accounts_by_provider.get(p, 0), cards_by_provider.get(p, 0))

                # Categorizar transações recentes
                from specialized_agents.banking_agent import BankingAgent
                temp_agent = BankingAgent()
                cat_totals: Dict[str, float] = defaultdict(float)
                for tx in view.recent_transactions:
                    if not tx.is_credit:
                        cat = temp_agent._auto_categorize(tx)
                        cat_totals[cat] += float(tx.amount)
                for cat, total in cat_totals.items():
                    self.record_category_spending(cat, total)

            except Exception as e:
                logger.warning(f"Erro ao coletar dados consolidados: {e}")

            # Alertas
            try:
                alerts = await agent.check_spending_alerts()
                warnings = sum(1 for a in alerts if a.severity == "warning")
                criticals = sum(1 for a in alerts if a.severity == "critical")
                self.update_spending_alerts_count(warnings, criticals)
                for alert in alerts:
                    self.record_spending_alert(
                        alert.category, float(alert.current_amount),
                        float(alert.threshold), alert.severity,
                    )
            except Exception as e:
                logger.warning(f"Erro ao coletar alertas: {e}")

            # Auth status
            for provider_enum, connector in agent._connectors.items():
                token = agent.security.get_cached_token(provider_enum.value)
                if token and not token.is_expired:
                    remaining = (token.issued_at + timedelta(seconds=token.expires_in) - datetime.now()).total_seconds()
                    self.record_auth_status(provider_enum.value, True, max(0, remaining))
                else:
                    self.record_auth_status(provider_enum.value, False, 0)

        except ImportError:
            logger.debug("Banking Agent não disponível para coleta de métricas")
        except Exception as e:
            logger.error(f"Erro na coleta de métricas banking: {e}")

    # ─────────── Output ───────────

    def get_metrics(self) -> bytes:
        """Retorna métricas em formato Prometheus."""
        return generate_latest(self.registry)

    def get_summary(self) -> dict:
        """Retorna resumo JSON das métricas."""
        return {
            "service": "eddie-banking-metrics",
            "version": "1.0.0",
            "last_collection": self._last_collection,
            "timestamp": datetime.now().isoformat(),
        }


# ─── Singleton ───

_banking_metrics: Optional[BankingMetricsExporter] = None


def get_banking_metrics() -> BankingMetricsExporter:
    global _banking_metrics
    if _banking_metrics is None:
        _banking_metrics = BankingMetricsExporter()
    return _banking_metrics


# ─── Background collection loop ───

async def banking_metrics_collection_loop(interval: int = 60):
    """Loop de coleta periódica de métricas do Banking Agent."""
    exporter = get_banking_metrics()
    logger.info(f"Banking metrics collection loop started (interval={interval}s)")
    while True:
        try:
            await exporter.collect_from_agent()
            exporter._last_collection = time.time()
        except Exception as e:
            logger.error(f"Banking metrics collection error: {e}")
        await asyncio.sleep(interval)


# ─── Standalone server ───

def start_standalone_server(port: int = 9102):
    """Inicia servidor Prometheus standalone na porta 9102."""
    exporter = get_banking_metrics()
    start_http_server(port, registry=exporter.registry)
    logger.info(f"Banking metrics exporter running on :{port}/metrics")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(banking_metrics_collection_loop(60))
    except KeyboardInterrupt:
        logger.info("Banking metrics exporter stopped")


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("BANKING_EXPORTER_PORT", 9104))
    start_standalone_server(port=port)
