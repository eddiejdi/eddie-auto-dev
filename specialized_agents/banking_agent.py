"""
Banking Integration Agent — Shared Auto-Dev

Agent orquestrador para integração multi-banco.
Gerencia conectores individuais (Santander, Itaú, Nubank, Mercado Pago),
consolidação de dados, e responde a comandos via bus de comunicação.

Funcionalidades:
  - Visão consolidada multi-banco (saldos, transações, cartões)
  - Extrato unificado com categorização
  - Alertas de gastos e anomalias
  - Relatórios financeiros
  - Transferências PIX
  - Integração com Telegram e dashboard Streamlit
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from .banking import (
    SantanderConnector,
    ItauConnector,
    NubankConnector,
    MercadoPagoConnector,
    BankingSecurityManager,
    BaseBankConnector,
    BankConnectionError,
    BankAuthError,
    BelvoConnector,
    get_belvo_connector,
)
from .banking.models import (
    BankAccount, Balance, Transaction, PixKey, PixTransfer,
    BankStatement, CreditCard, Invoice, ConsolidatedView,
    BankProvider, TransactionType,
)

# Bus de comunicação (opcional)
try:
    from .agent_communication_bus import (
        get_communication_bus, MessageType,
        log_request, log_response, log_task_start, log_task_end, log_error,
    )
    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False

# Memória do agent (opcional)
try:
    from .agent_memory import get_agent_memory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

logger = logging.getLogger("shared.banking_agent")

# Diretório de dados
DATA_DIR = Path(__file__).parent.parent / "agent_data" / "banking"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SpendingAlert:
    """Alerta de gastos"""
    provider: BankProvider
    category: str
    current_amount: Decimal
    threshold: Decimal
    period: str
    message: str
    severity: str = "warning"  # info, warning, critical


class BankingAgent:
    """
    Agent de integração bancária multi-banco.

    Orquestra conectores individuais e fornece:
    - Visão consolidada de todas as contas
    - Extrato unificado com categorização inteligente
    - Alertas e regras de negócio
    - Relatórios consolidados
    - Interface para Telegram / Streamlit
    """

    AGENT_NAME = "banking_agent"
    SUPPORTED_PROVIDERS = [
        BankProvider.SANTANDER,
        BankProvider.ITAU,
        BankProvider.NUBANK,
        BankProvider.MERCADOPAGO,
    ]

    def __init__(self):
        self.security = BankingSecurityManager(DATA_DIR)
        self._connectors: Dict[BankProvider, BaseBankConnector] = {}
        self._spending_thresholds: Dict[str, Decimal] = {}
        self._initialized = False

        # Belvo connector (para Santander, Itaú, Nubank via Open Finance)
        self._belvo: Optional[BelvoConnector] = None
        self._belvo_enabled = False

        # Registrar no bus de comunicação
        if BUS_AVAILABLE:
            try:
                bus = get_communication_bus()
                bus.subscribe(self._on_bus_message)
            except Exception:
                pass

    # ──────────── Inicialização ────────────

    async def initialize(self, providers: Optional[List[BankProvider]] = None):
        """
        Inicializa conectores para os bancos solicitados.

        Estratégia:
          - Se Belvo estiver configurado → usa Belvo para Santander, Itaú, Nubank
          - Mercado Pago → sempre via conector direto (API proprietária)
          - Fallback: tenta conector direto (requer certificados mTLS/ITP)
        """
        if BUS_AVAILABLE:
            log_task_start(self.AGENT_NAME, "banking_init", "Inicializando Banking Agent")

        target_providers = providers or self.SUPPORTED_PROVIDERS
        results: Dict[str, str] = {}

        # 1) Inicializar Belvo para bancos OFB
        belvo_banks = {BankProvider.SANTANDER, BankProvider.ITAU, BankProvider.NUBANK}
        belvo_targets = [p for p in target_providers if p in belvo_banks]

        if belvo_targets:
            try:
                self._belvo = get_belvo_connector()
                if self._belvo.is_configured:
                    health = await self._belvo.health_check()
                    if "error" not in health or health.get("total_connected", 0) >= 0:
                        self._belvo_enabled = True
                        # Verificar links existentes
                        connected = await self._belvo.get_connected_banks()
                        for provider in belvo_targets:
                            if provider in connected:
                                results[provider.value] = f"OK (Belvo: {connected[provider]['status']})"
                            else:
                                results[provider.value] = "Belvo OK — link pendente (vincule via widget)"
                        logger.info(f"Belvo habilitado: {len(connected)} bancos conectados")
                    else:
                        logger.warning(f"Belvo health check falhou: {health.get('error')}")
                        results["belvo"] = f"Error: {health.get('error')}"
                else:
                    logger.info("Belvo não configurado — configure BELVO_SECRET_ID e BELVO_SECRET_PASSWORD")
                    results["belvo"] = "Não configurado"
            except Exception as e:
                logger.warning(f"Belvo init falhou: {e}")
                results["belvo"] = f"Error: {e}"

        # 2) Fallback: tentar conectores diretos para bancos OFB não resolvidos pelo Belvo
        if not self._belvo_enabled:
            for provider in belvo_targets:
                if provider.value not in results or "Error" in results.get(provider.value, ""):
                    try:
                        connector = self._create_connector(provider)
                        await connector.authenticate()
                        self._connectors[provider] = connector
                        results[provider.value] = "OK (direto)"
                        logger.info(f"Banking Agent: {provider.value} conectado (direto)")
                    except (BankAuthError, Exception) as e:
                        results[provider.value] = f"Falhou: {e}"
                        logger.warning(f"Banking Agent: {provider.value} direto falhou: {e}")

        # 3) Mercado Pago — sempre conector direto
        if BankProvider.MERCADOPAGO in target_providers:
            try:
                connector = self._create_connector(BankProvider.MERCADOPAGO)
                await connector.authenticate()
                self._connectors[BankProvider.MERCADOPAGO] = connector
                results[BankProvider.MERCADOPAGO.value] = "OK"
                logger.info("Banking Agent: mercadopago conectado")
            except Exception as e:
                results[BankProvider.MERCADOPAGO.value] = f"Error: {e}"
                logger.warning(f"Banking Agent: mercadopago falhou: {e}")

        self._initialized = True

        if BUS_AVAILABLE:
            belvo_str = " (Belvo ativo)" if self._belvo_enabled else ""
            connected_count = len(self._connectors) + (len(await self._belvo.get_connected_banks()) if self._belvo_enabled else 0)
            log_task_end(
                self.AGENT_NAME, "banking_init",
                f"Banking Agent inicializado{belvo_str}: {connected_count} bancos conectados"
            )

        return results

    def _create_connector(self, provider: BankProvider) -> BaseBankConnector:
        """Factory para criar o conector correto."""
        connectors = {
            BankProvider.SANTANDER: SantanderConnector,
            BankProvider.ITAU: ItauConnector,
            BankProvider.NUBANK: NubankConnector,
            BankProvider.MERCADOPAGO: MercadoPagoConnector,
        }
        cls = connectors.get(provider)
        if not cls:
            raise ValueError(f"Provider não suportado: {provider}")
        return cls(security=self.security, sandbox=True)

    @property
    def connected_providers(self) -> List[str]:
        """Lista de bancos conectados."""
        return [p.value for p in self._connectors.keys()]

    # ──────────── Visão Consolidada ────────────

    async def get_consolidated_view(self) -> ConsolidatedView:
        """
        Retorna visão consolidada de TODOS os bancos conectados:
        contas, saldos, transações recentes, cartões e chaves PIX.
        Usa Belvo para bancos OFB + conectores diretos para Mercado Pago.
        """
        if BUS_AVAILABLE:
            log_request(self.AGENT_NAME, "all_banks", "consolidated_view")

        view = ConsolidatedView()

        # 1) Dados via Belvo (Santander, Itaú, Nubank)
        if self._belvo_enabled and self._belvo:
            try:
                belvo_accounts = await self._belvo.get_all_accounts()
                belvo_balances = await self._belvo.get_all_balances()
                belvo_txs = await self._belvo.get_all_transactions()
                view.accounts.extend(belvo_accounts)
                view.balances.extend(belvo_balances)
                view.recent_transactions.extend(belvo_txs)
            except Exception as e:
                logger.error(f"Erro ao coletar dados Belvo: {e}")

        # 2) Dados via conectores diretos (Mercado Pago + fallback)
        tasks = []
        for provider, connector in self._connectors.items():
            tasks.append(self._collect_provider_data(provider, connector))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Erro ao coletar dados: {result}")
                continue
            accounts, balances, transactions, cards, pix_keys = result
            view.accounts.extend(accounts)
            view.balances.extend(balances)
            view.recent_transactions.extend(transactions)
            view.credit_cards.extend(cards)
            view.pix_keys.extend(pix_keys)

        # Ordenar transações por data (mais recente primeiro)
        view.recent_transactions.sort(key=lambda t: t.date, reverse=True)

        if BUS_AVAILABLE:
            log_response(
                self.AGENT_NAME, "all_banks",
                f"Consolidado: {len(view.accounts)} contas, R$ {view.total_available:,.2f} disponível"
            )

        return view

    async def _collect_provider_data(
        self, provider: BankProvider, connector: BaseBankConnector
    ) -> Tuple[List[BankAccount], List[Balance], List[Transaction], List[CreditCard], List[PixKey]]:
        """Coleta todos os dados de um provider."""
        accounts: List[BankAccount] = []
        balances: List[Balance] = []
        transactions: List[Transaction] = []
        cards: List[CreditCard] = []
        pix_keys: List[PixKey] = []

        try:
            accounts = await connector.get_accounts()
        except Exception as e:
            logger.warning(f"[{provider.value}] Erro ao listar contas: {e}")

        # Saldo e transações para cada conta
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        for acc in accounts:
            try:
                bal = await connector.get_balance(acc.id)
                balances.append(bal)
            except Exception as e:
                logger.warning(f"[{provider.value}] Saldo falhou para {acc.id}: {e}")

            try:
                txs = await connector.get_transactions(acc.id, start_date, end_date)
                transactions.extend(txs)
            except Exception as e:
                logger.warning(f"[{provider.value}] Transações falharam para {acc.id}: {e}")

            try:
                keys = await connector.get_pix_keys(acc.id)
                pix_keys.extend(keys)
            except Exception:
                pass

        # Cartões
        try:
            cards = await connector.get_credit_cards()
        except Exception:
            pass

        return accounts, balances, transactions, cards, pix_keys

    # ──────────── Extrato Unificado ────────────

    async def get_unified_statement(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        providers: Optional[List[BankProvider]] = None,
    ) -> Dict[str, Any]:
        """
        Gera extrato unificado de todos os bancos (ou bancos selecionados).
        """
        end_date = end_date or date.today()
        start_date = start_date or end_date - timedelta(days=30)
        target = providers or list(self._connectors.keys())

        all_transactions: List[Transaction] = []
        all_statements: List[Dict] = []

        for provider in target:
            connector = self._connectors.get(provider)
            if not connector:
                continue
            try:
                accounts = await connector.get_accounts()
                for acc in accounts:
                    stmt = await connector.get_statement(acc.id, start_date, end_date)
                    all_transactions.extend(stmt.transactions)
                    all_statements.append(stmt.to_dict())
            except Exception as e:
                logger.warning(f"[{provider.value}] Extrato falhou: {e}")

        # Categorizar transações
        categorized = self._categorize_transactions(all_transactions)

        # Calcular totais
        total_credits = sum(t.amount for t in all_transactions if t.is_credit)
        total_debits = sum(t.amount for t in all_transactions if not t.is_credit)

        return {
            "period": f"{start_date.isoformat()} a {end_date.isoformat()}",
            "providers": [p.value for p in target],
            "total_credits": str(total_credits),
            "total_debits": str(total_debits),
            "net_result": str(total_credits - total_debits),
            "transaction_count": len(all_transactions),
            "by_category": categorized,
            "statements": all_statements,
            "transactions": [t.to_dict() for t in sorted(all_transactions, key=lambda t: t.date, reverse=True)[:100]],
        }

    def _categorize_transactions(self, transactions: List[Transaction]) -> Dict[str, Dict]:
        """Agrupa transações por categoria com totais."""
        categories: Dict[str, Dict] = {}

        for t in transactions:
            cat = t.category or self._auto_categorize(t)
            if cat not in categories:
                categories[cat] = {"count": 0, "total_credit": Decimal("0"), "total_debit": Decimal("0")}
            categories[cat]["count"] += 1
            if t.is_credit:
                categories[cat]["total_credit"] += t.amount
            else:
                categories[cat]["total_debit"] += t.amount

        # Converter Decimal para string
        return {
            k: {"count": v["count"], "total_credit": str(v["total_credit"]), "total_debit": str(v["total_debit"])}
            for k, v in categories.items()
        }

    @staticmethod
    def _auto_categorize(transaction: Transaction) -> str:
        """Categoriza transação automaticamente baseado na descrição."""
        desc = transaction.description.lower()
        rules = {
            "Alimentação": ["ifood", "rappi", "uber eats", "restaurante", "lanchonete", "padaria", "mercado", "supermercado", "pão de açucar", "carrefour", "assaí"],
            "Transporte": ["uber", "99", "cabify", "estacionamento", "posto", "combustível", "shell", "ipiranga", "gasolina", "pedagio"],
            "Moradia": ["aluguel", "condomínio", "iptu", "energia", "luz", "agua", "gás", "internet"],
            "Saúde": ["farmácia", "hospital", "médico", "clínica", "drogaria", "unimed", "amil"],
            "Educação": ["curso", "escola", "faculdade", "udemy", "alura", "mensalidade"],
            "Lazer": ["netflix", "spotify", "disney", "hbo", "cinema", "teatro", "show"],
            "Compras": ["amazon", "mercado livre", "magalu", "shopee", "americanas", "casas bahia"],
            "Transferência": ["pix", "ted", "transferência", "transferencia"],
            "Salário": ["salário", "salario", "folha", "pgto ref"],
            "Tarifas": ["tarifa", "taxa", "anuidade", "iof"],
        }

        for category, keywords in rules.items():
            if any(kw in desc for kw in keywords):
                return category

        if transaction.type == TransactionType.FEE:
            return "Tarifas"
        if transaction.type in (TransactionType.PIX_SENT, TransactionType.PIX_RECEIVED):
            return "Transferência"

        return "Outros"

    # ──────────── Alertas ────────────

    async def check_spending_alerts(self) -> List[SpendingAlert]:
        """Verifica regras de gasto e gera alertas."""
        alerts: List[SpendingAlert] = []
        end_date = date.today()
        start_date = end_date.replace(day=1)  # Início do mês

        for provider, connector in self._connectors.items():
            try:
                accounts = await connector.get_accounts()
                for acc in accounts:
                    transactions = await connector.get_transactions(acc.id, start_date, end_date)
                    # Verificar thresholds por categoria
                    cat_totals: Dict[str, Decimal] = {}
                    for t in transactions:
                        if not t.is_credit:
                            cat = self._auto_categorize(t)
                            cat_totals[cat] = cat_totals.get(cat, Decimal("0")) + t.amount

                    for cat, total in cat_totals.items():
                        threshold = self._spending_thresholds.get(cat, Decimal("0"))
                        if threshold > 0 and total > threshold:
                            alerts.append(SpendingAlert(
                                provider=provider,
                                category=cat,
                                current_amount=total,
                                threshold=threshold,
                                period=f"{start_date.isoformat()} a {end_date.isoformat()}",
                                message=f"Gastos com {cat} (R$ {total:,.2f}) ultrapassaram limite de R$ {threshold:,.2f}",
                                severity="critical" if total > threshold * Decimal("1.5") else "warning",
                            ))
            except Exception as e:
                logger.warning(f"Alerta check falhou para {provider.value}: {e}")

        return alerts

    def set_spending_threshold(self, category: str, amount: Decimal):
        """Define limite de gasto mensal por categoria."""
        self._spending_thresholds[category] = amount

    # ──────────── PIX ────────────

    async def send_pix(
        self,
        from_provider: BankProvider,
        pix_key: str,
        amount: Decimal,
        description: Optional[str] = None,
    ) -> PixTransfer:
        """
        Envia PIX a partir de um banco específico.
        Requer consentimento prévio (Open Finance) ou token adequado (Mercado Pago).
        """
        connector = self._connectors.get(from_provider)
        if not connector:
            raise ValueError(f"Provider {from_provider.value} não está conectado")

        if BUS_AVAILABLE:
            log_request(
                self.AGENT_NAME, from_provider.value,
                f"PIX R$ {amount} → {self.security.mask_account(pix_key)}"
            )

        transfer = PixTransfer(
            id=connector._generate_id(),
            source_account_id="",
            destination_key=pix_key,
            destination_key_type=self._detect_pix_key_type(pix_key),
            amount=amount,
            description=description,
        )

        result = await connector.initiate_pix(transfer)

        # Registrar na memória do agent
        if MEMORY_AVAILABLE:
            try:
                memory = get_agent_memory()
                memory.record_decision(
                    agent_name=self.AGENT_NAME,
                    decision_type="pix_transfer",
                    context=f"PIX R$ {amount} via {from_provider.value} → {pix_key[:10]}...",
                    decision=f"Status: {result.status}",
                    confidence=1.0 if result.status == "COMPLETED" else 0.5,
                )
            except Exception:
                pass

        if BUS_AVAILABLE:
            log_response(
                self.AGENT_NAME, from_provider.value,
                f"PIX {result.status}: E2E={result.end_to_end_id or 'N/A'}"
            )

        return result

    @staticmethod
    def _detect_pix_key_type(key: str):
        """Detecta tipo de chave PIX automaticamente."""
        from .banking.models import PixKeyType
        import re

        digits = "".join(c for c in key if c.isdigit())
        if len(digits) == 11 and not "@" in key:
            return PixKeyType.CPF
        if len(digits) == 14:
            return PixKeyType.CNPJ
        if "@" in key:
            return PixKeyType.EMAIL
        if key.startswith("+55") or (len(digits) in (10, 11) and digits[0] != "0"):
            return PixKeyType.PHONE
        return PixKeyType.EVP

    # ──────────── Relatórios ────────────

    async def generate_monthly_report(
        self, month: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera relatório mensal consolidado.
        month: formato "2026-02"
        """
        if month:
            year, m = month.split("-")
            start = date(int(year), int(m), 1)
            if int(m) == 12:
                end = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(int(year), int(m) + 1, 1) - timedelta(days=1)
        else:
            today = date.today()
            start = today.replace(day=1)
            end = today

        statement = await self.get_unified_statement(start, end)
        alerts = await self.check_spending_alerts()
        view = await self.get_consolidated_view()

        return {
            "report_type": "monthly",
            "period": f"{start.isoformat()} a {end.isoformat()}",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_available": str(view.total_available),
                "total_credit_limit": str(view.total_credit_limit),
                "connected_banks": self.connected_providers,
                "total_accounts": len(view.accounts),
            },
            "financials": {
                "total_income": statement["total_credits"],
                "total_expenses": statement["total_debits"],
                "net_result": statement["net_result"],
                "transactions": statement["transaction_count"],
            },
            "spending_by_category": statement["by_category"],
            "alerts": [
                {"category": a.category, "amount": str(a.current_amount), "threshold": str(a.threshold), "message": a.message}
                for a in alerts
            ],
        }

    # ──────────── Interface Telegram ────────────

    async def handle_telegram_command(self, command: str, args: str = "") -> str:
        """
        Processa comandos do Telegram relacionados a banking.

        Comandos suportados:
          /saldo          — Saldo de todos os bancos
          /extrato [dias] — Extrato dos últimos N dias
          /pix info       — Minhas chaves PIX
          /cartoes        — Cartões de crédito
          /relatorio      — Relatório mensal
          /alertas        — Alertas de gastos
          /bancos         — Status das conexões bancárias
        """
        try:
            if command == "/bancos":
                lines = ["🏦 **Status das Conexões Bancárias**\n"]
                # Belvo
                if self._belvo_enabled and self._belvo:
                    banks = await self._belvo.get_connected_banks()
                    lines.append(f"🔗 **Belvo** ({self._belvo.environment}): ✅ ativo")
                    for provider, info in banks.items():
                        status_icon = "✅" if info["status"] in ("valid", "active") else "⚠️"
                        lines.append(f"  {status_icon} {provider.value.title()}: {info['status']}")
                    if not banks:
                        lines.append("  ⚠️ Nenhum banco vinculado — use o widget para conectar")
                else:
                    lines.append("❌ **Belvo**: não configurado")
                    lines.append("  Configure BELVO_SECRET_ID e BELVO_SECRET_PASSWORD")

                # Conectores diretos
                if self._connectors:
                    lines.append(f"\n📡 **Conectores diretos:**")
                    for provider in self._connectors:
                        lines.append(f"  ✅ {provider.value.title()}")

                return "\n".join(lines)

            elif command == "/saldo":
                view = await self.get_consolidated_view()
                return view.summary_text()

            elif command == "/extrato":
                days = int(args) if args.strip().isdigit() else 7
                end = date.today()
                start = end - timedelta(days=days)
                stmt = await self.get_unified_statement(start, end)
                lines = [
                    f"📋 **Extrato Unificado** ({days} dias)",
                    f"💰 Entradas: R$ {stmt['total_credits']}",
                    f"💸 Saídas: R$ {stmt['total_debits']}",
                    f"📊 Resultado: R$ {stmt['net_result']}",
                    f"📝 {stmt['transaction_count']} transações",
                ]
                if stmt["by_category"]:
                    lines.append("\n**Por Categoria:**")
                    for cat, data in list(stmt["by_category"].items())[:8]:
                        lines.append(f"  • {cat}: R$ {data['total_debit']} ({data['count']}x)")
                return "\n".join(lines)

            elif command == "/cartoes":
                view = await self.get_consolidated_view()
                if not view.credit_cards:
                    return "💳 Nenhum cartão de crédito encontrado."
                lines = ["💳 **Cartões de Crédito**"]
                for c in view.credit_cards:
                    lines.append(
                        f"  • {c.provider.value.title()} ****{c.last_four_digits} "
                        f"({c.brand.value}): Limite R$ {c.available_limit:,.2f} / R$ {c.credit_limit:,.2f}"
                    )
                return "\n".join(lines)

            elif command == "/relatorio":
                report = await self.generate_monthly_report(args if args else None)
                lines = [
                    f"📊 **Relatório Mensal** — {report['period']}",
                    f"💵 Renda: R$ {report['financials']['total_income']}",
                    f"💸 Gastos: R$ {report['financials']['total_expenses']}",
                    f"📈 Resultado: R$ {report['financials']['net_result']}",
                    f"🏦 Saldo Total: R$ {report['summary']['total_available']}",
                ]
                if report["alerts"]:
                    lines.append(f"\n⚠️ **{len(report['alerts'])} Alertas:**")
                    for a in report["alerts"]:
                        lines.append(f"  • {a['message']}")
                return "\n".join(lines)

            elif command == "/alertas":
                alerts = await self.check_spending_alerts()
                if not alerts:
                    return "✅ Nenhum alerta de gastos."
                lines = [f"⚠️ **{len(alerts)} Alertas de Gastos**"]
                for a in alerts:
                    emoji = "🔴" if a.severity == "critical" else "🟡"
                    lines.append(f"{emoji} {a.message}")
                return "\n".join(lines)

            else:
                return (
                    "🏦 **Shared Banking Agent**\n\n"
                    "Comandos disponíveis:\n"
                    "  /bancos — Status das conexões\n"
                    "  /saldo — Saldo consolidado\n"
                    "  /extrato [dias] — Extrato unificado\n"
                    "  /cartoes — Cartões de crédito\n"
                    "  /relatorio [YYYY-MM] — Relatório mensal\n"
                    "  /alertas — Alertas de gastos"
                )

        except Exception as e:
            logger.error(f"Banking command error: {e}")
            return f"❌ Erro ao processar comando: {e}"

    # ──────────── Bus de Comunicação ────────────

    def _on_bus_message(self, message):
        """Callback para mensagens do bus direcionadas ao banking agent."""
        if hasattr(message, 'target') and message.target == self.AGENT_NAME:
            content = message.content if isinstance(message.content, str) else str(message.content)
            # Processar assíncronamente
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._process_bus_message(content, message.metadata))
            except RuntimeError:
                pass

    async def _process_bus_message(self, content: str, metadata: Dict):
        """Processa mensagem recebida pelo bus."""
        if content.startswith("/"):
            parts = content.split(" ", 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            response = await self.handle_telegram_command(cmd, args)
            if BUS_AVAILABLE:
                log_response(self.AGENT_NAME, metadata.get("source", "unknown"), response[:500])

    # ──────────── Cleanup ────────────

    async def close(self):
        """Fecha todas as conexões."""
        for connector in self._connectors.values():
            await connector.close()
        self._connectors.clear()
        if self._belvo:
            await self._belvo.close()
            self._belvo = None
            self._belvo_enabled = False


# Singleton
_banking_agent_instance: Optional[BankingAgent] = None


def get_banking_agent() -> BankingAgent:
    """Retorna instância singleton do Banking Agent."""
    global _banking_agent_instance
    if _banking_agent_instance is None:
        _banking_agent_instance = BankingAgent()
    return _banking_agent_instance
