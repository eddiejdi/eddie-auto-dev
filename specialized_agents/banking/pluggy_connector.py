"""
Conector Pluggy — Agregador Open Finance Brasil.

Usa a API da Pluggy (https://pluggy.ai) como intermediário para
acessar dados bancários via Open Finance (Nubank, Itaú, Bradesco, etc.).

Fluxo de configuração:
  1. Cadastre-se em https://meu.pluggy.ai → conecte seus bancos via Open Finance
  2. Crie conta dev em https://dashboard.pluggy.ai → obtenha CLIENT_ID e CLIENT_SECRET
  3. Vincule sua conta MeuPluggy à Application via Demo/OAuth
  4. Use o item_id gerado para buscar dados

Variáveis de ambiente:
  PLUGGY_CLIENT_ID       — Client ID da application Pluggy
  PLUGGY_CLIENT_SECRET   — Client Secret da application Pluggy
  PLUGGY_ITEM_IDS        — JSON dict: {"nubank": "uuid", "itau": "uuid", ...}

Documentação: https://docs.pluggy.ai/reference
"""

import os
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

import httpx

from .models import (
    BankAccount, Balance, Transaction, CreditCard, Invoice,
    BankStatement, BankProvider, AccountType, TransactionType, CardBrand,
)
from .security import BankingSecurityManager

logger = logging.getLogger("eddie.banking.pluggy")

# ──────────── Constantes ────────────

PLUGGY_API_URL = "https://api.pluggy.ai"

# Mapeamento connector ID → BankProvider
PLUGGY_CONNECTOR_MAP: Dict[int, BankProvider] = {
    212: BankProvider.NUBANK,       # Nubank
    201: BankProvider.ITAU,         # Itaú
    # Podem ser adicionados conforme novos bancos forem conectados
}

# Mapeamento nome → BankProvider (backup, case-insensitive)
PLUGGY_NAME_MAP: Dict[str, BankProvider] = {
    "nubank": BankProvider.NUBANK,
    "itaú": BankProvider.ITAU,
    "itau": BankProvider.ITAU,
    "santander": BankProvider.SANTANDER,
    "mercadopago": BankProvider.MERCADOPAGO,
    "mercado pago": BankProvider.MERCADOPAGO,
}

# Mapeamento Pluggy account type → nosso AccountType
PLUGGY_ACCOUNT_TYPE_MAP: Dict[str, AccountType] = {
    "BANK": AccountType.CONTA_CORRENTE,
    "CHECKING": AccountType.CONTA_CORRENTE,
    "SAVINGS": AccountType.POUPANCA,
    "CREDIT": AccountType.PAGAMENTO,  # Cartão de crédito → genérico
}

# Mapeamento Pluggy card brand → nosso CardBrand
PLUGGY_BRAND_MAP: Dict[str, CardBrand] = {
    "VISA": CardBrand.VISA,
    "MASTERCARD": CardBrand.MASTERCARD,
    "ELO": CardBrand.ELO,
    "AMEX": CardBrand.AMEX,
    "HIPERCARD": CardBrand.HIPERCARD,
    "AMERICAN EXPRESS": CardBrand.AMEX,
}


class PluggyConnectionError(Exception):
    """Erro de conexão com Pluggy API."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(f"[Pluggy] {message}" + (f" (HTTP {status_code})" if status_code else ""))


class PluggyConnector:
    """
    Conector unificado via Pluggy para bancos brasileiros Open Finance.

    Gerencia múltiplos items (Nubank, Itaú, etc.) através de uma
    interface única que converte dados Pluggy → modelos Eddie Banking.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        item_ids: Optional[Dict[str, str]] = None,
    ):
        """
        Args:
            client_id: Pluggy Application client_id
            client_secret: Pluggy Application client_secret
            item_ids: Dict mapping bank name → Pluggy item UUID
                      Ex: {"nubank": "abc-123", "itau": "def-456"}
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._item_ids = item_ids or {}
        self._api_key: Optional[str] = None
        self._api_key_expires: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._security = BankingSecurityManager()

        # Carregar do vault se não informado
        if not self._client_id or not self._client_secret:
            self._load_credentials()

    def _load_credentials(self):
        """Carrega credenciais do vault Eddie ou variáveis de ambiente."""
        # Tentar vault primeiro
        try:
            creds = self._security.load_credentials("pluggy")
            if creds:
                self._client_id = creds.get("client_id", self._client_id)
                self._client_secret = creds.get("client_secret", self._client_secret)
                items_json = creds.get("item_ids", "{}")
                if isinstance(items_json, str):
                    self._item_ids = json.loads(items_json)
                elif isinstance(items_json, dict):
                    self._item_ids = items_json
                logger.info("Credenciais Pluggy carregadas do vault")
                return
        except Exception as e:
            logger.debug(f"Vault não disponível: {e}")

        # Fallback: variáveis de ambiente
        self._client_id = self._client_id or os.getenv("PLUGGY_CLIENT_ID", "")
        self._client_secret = self._client_secret or os.getenv("PLUGGY_CLIENT_SECRET", "")
        items_env = os.getenv("PLUGGY_ITEM_IDS", "{}")
        if not self._item_ids:
            try:
                self._item_ids = json.loads(items_env)
            except json.JSONDecodeError:
                self._item_ids = {}

        # Fallback 2: Secrets Agent (se ainda não temos credenciais)
        if not self._client_id or not self._client_secret:
            try:
                from tools.secrets_agent_client import get_secrets_agent_client
                client = get_secrets_agent_client()
                if client:
                    client_id_sa = client.get_secret("pluggy-client-id")
                    client_secret_sa = client.get_secret("pluggy-client-secret")
                    if client_id_sa:
                        self._client_id = client_id_sa
                    if client_secret_sa:
                        self._client_secret = client_secret_sa
                    if client_id_sa and client_secret_sa:
                        logger.info("Credenciais Pluggy carregadas do Secrets Agent")
            except Exception as e:
                logger.debug(f"Secrets Agent não disponível para Pluggy: {e}")

    @property
    def is_configured(self) -> bool:
        """Verifica se as credenciais estão configuradas."""
        return bool(self._client_id and self._client_secret)

    @property
    def has_items(self) -> bool:
        """Verifica se há itens (bancos) conectados."""
        return bool(self._item_ids)

    @property
    def connected_banks(self) -> List[str]:
        """Retorna lista de bancos conectados."""
        return list(self._item_ids.keys())

    # ──────────── HTTP Client ────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna client HTTP configurado."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=PLUGGY_API_URL,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Fecha o client HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ──────────── Autenticação ────────────

    async def _ensure_api_key(self):
        """Garante que temos um API key válido."""
        if self._api_key and self._api_key_expires and datetime.now() < self._api_key_expires:
            return  # Token ainda válido

        if not self.is_configured:
            raise PluggyConnectionError(
                "Credenciais Pluggy não configuradas. "
                "Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET ou salve no vault."
            )

        client = await self._get_client()
        resp = await client.post("/auth", json={
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
        })

        if resp.status_code != 200:
            raise PluggyConnectionError(
                f"Falha na autenticação: {resp.text}", resp.status_code
            )

        data = resp.json()
        self._api_key = data.get("apiKey")
        # Token Pluggy dura ~2h, renovar com margem
        self._api_key_expires = datetime.now() + timedelta(hours=1, minutes=50)
        logger.info("API key Pluggy obtida com sucesso")

    async def _headers(self) -> Dict[str, str]:
        """Headers com autenticação."""
        await self._ensure_api_key()
        return {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET request autenticado."""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.get(path, headers=headers, params=params)

        if resp.status_code == 404:
            return {}
        if resp.status_code >= 400:
            raise PluggyConnectionError(
                f"GET {path}: {resp.text}", resp.status_code
            )
        return resp.json()

    async def _post(self, path: str, payload: Dict) -> Dict[str, Any]:
        """POST request autenticado."""
        client = await self._get_client()
        headers = await self._headers()
        resp = await client.post(path, headers=headers, json=payload)

        if resp.status_code >= 400:
            raise PluggyConnectionError(
                f"POST {path}: {resp.text}", resp.status_code
            )
        return resp.json()

    # ──────────── Helpers ────────────

    def _resolve_provider(self, item_data: Dict) -> BankProvider:
        """Resolve BankProvider a partir de dados do item Pluggy."""
        connector_id = item_data.get("connector", {}).get("id", 0)
        if connector_id in PLUGGY_CONNECTOR_MAP:
            return PLUGGY_CONNECTOR_MAP[connector_id]

        name = item_data.get("connector", {}).get("name", "").lower()
        for key, provider in PLUGGY_NAME_MAP.items():
            if key in name:
                return provider

        return BankProvider.NUBANK  # fallback

    def _get_item_id(self, bank: str) -> str:
        """Resolve item_id de um banco."""
        bank_lower = bank.lower().strip()
        if bank_lower in self._item_ids:
            return self._item_ids[bank_lower]
        # Tentar match parcial
        for key, item_id in self._item_ids.items():
            if bank_lower in key.lower() or key.lower() in bank_lower:
                return item_id
        raise PluggyConnectionError(
            f"Banco '{bank}' não encontrado. Bancos disponíveis: {list(self._item_ids.keys())}"
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse data da API Pluggy."""
        if not date_str:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _classify_transaction(self, pluggy_tx: Dict) -> TransactionType:
        """Classifica tipo de transação a partir dos dados Pluggy."""
        tx_type = pluggy_tx.get("type", "").upper()
        desc = (pluggy_tx.get("description") or "").upper()
        category = (pluggy_tx.get("category") or "").upper()

        if "PIX" in desc:
            amount = pluggy_tx.get("amount", 0)
            return TransactionType.PIX_RECEIVED if amount > 0 else TransactionType.PIX_SENT
        if "TED" in desc or "DOC" in desc:
            amount = pluggy_tx.get("amount", 0)
            return TransactionType.TED_RECEIVED if amount > 0 else TransactionType.TED_SENT
        if "BOLETO" in desc:
            return TransactionType.BOLETO_PAYMENT
        if "ESTORNO" in desc or "REFUND" in category:
            return TransactionType.REFUND
        if "TARIFA" in desc or "TAX" in category:
            return TransactionType.FEE
        if "JUROS" in desc or "INTEREST" in category:
            return TransactionType.INTEREST
        if "SALARIO" in desc or "SALARY" in category:
            return TransactionType.SALARY
        if any(x in desc for x in ("COMPRA", "PURCHASE", "PAGAMENTO")):
            return TransactionType.CARD_PURCHASE

        amount = pluggy_tx.get("amount", 0)
        if amount > 0:
            return TransactionType.CREDIT
        return TransactionType.DEBIT

    def _resolve_brand(self, brand_str: Optional[str]) -> CardBrand:
        """Resolve bandeira do cartão."""
        if not brand_str:
            return CardBrand.OTHER
        upper = brand_str.upper()
        return PLUGGY_BRAND_MAP.get(upper, CardBrand.OTHER)

    # ──────────── API: Verificação ────────────

    async def verify_connection(self) -> Dict[str, Any]:
        """
        Verifica conexão com a API e status dos itens.

        Returns:
            Dict com status de cada banco conectado.
        """
        await self._ensure_api_key()
        result = {"authenticated": True, "items": {}}

        for bank, item_id in self._item_ids.items():
            try:
                item = await self._get(f"/items/{item_id}")
                result["items"][bank] = {
                    "status": item.get("status"),
                    "connector": item.get("connector", {}).get("name"),
                    "last_updated": item.get("lastUpdatedAt"),
                    "execution_status": item.get("executionStatus"),
                }
            except PluggyConnectionError as e:
                result["items"][bank] = {"status": "ERROR", "error": str(e)}

        return result

    # ──────────── API: Contas ────────────

    async def get_accounts(self, bank: Optional[str] = None) -> List[BankAccount]:
        """
        Lista contas de um banco ou de todos os bancos conectados.

        Args:
            bank: Nome do banco (nubank, itau, etc.) ou None para todos.

        Returns:
            Lista de BankAccount.
        """
        accounts = []
        targets = {bank: self._get_item_id(bank)} if bank else self._item_ids

        for bank_name, item_id in targets.items():
            try:
                data = await self._get(f"/accounts", params={"itemId": item_id})
                for acc in data.get("results", []):
                    # Buscar item para resolver provider
                    item_data = await self._get(f"/items/{item_id}")
                    provider = self._resolve_provider(item_data)

                    acc_type = PLUGGY_ACCOUNT_TYPE_MAP.get(
                        acc.get("type", "").upper(),
                        AccountType.CONTA_CORRENTE
                    )

                    accounts.append(BankAccount(
                        id=acc.get("id", ""),
                        provider=provider,
                        account_type=acc_type,
                        branch=acc.get("bankData", {}).get("transferNumber", "") if acc.get("bankData") else "",
                        number=acc.get("number", ""),
                        holder_name=acc.get("owner", ""),
                        holder_document=acc.get("taxNumber", "***"),
                        currency=acc.get("currencyCode", "BRL"),
                        status="ACTIVE",
                        metadata={
                            "pluggy_item_id": item_id,
                            "bank_name": bank_name,
                            "subtype": acc.get("subtype"),
                            "marketing_name": acc.get("marketingName"),
                        },
                    ))
            except PluggyConnectionError as e:
                logger.error(f"Erro ao buscar contas de {bank_name}: {e}")

        return accounts

    # ──────────── API: Saldos ────────────

    async def get_balance(self, account_id: str, bank: Optional[str] = None) -> Optional[Balance]:
        """
        Busca saldo de uma conta específica.

        Args:
            account_id: ID da conta Pluggy
            bank: (opcional) Nome do banco para resolver provider

        Returns:
            Balance ou None
        """
        try:
            acc = await self._get(f"/accounts/{account_id}")
            if not acc:
                return None

            item_id = acc.get("itemId", "")
            item_data = await self._get(f"/items/{item_id}")
            provider = self._resolve_provider(item_data)

            return Balance(
                account_id=account_id,
                provider=provider,
                available=Decimal(str(acc.get("balance", 0))),
                currency=acc.get("currencyCode", "BRL"),
            )
        except PluggyConnectionError as e:
            logger.error(f"Erro ao buscar saldo: {e}")
            return None

    async def get_all_balances(self) -> List[Balance]:
        """Busca saldos de todas as contas conectadas."""
        balances = []
        accounts = await self.get_accounts()
        for acc in accounts:
            bal = await self.get_balance(acc.id)
            if bal:
                balances.append(bal)
        return balances

    # ──────────── API: Transações ────────────

    async def get_transactions(
        self,
        account_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page_size: int = 500,
    ) -> List[Transaction]:
        """
        Busca transações de uma conta.

        Args:
            account_id: ID da conta Pluggy
            date_from: Data inicial (padrão: 90 dias atrás)
            date_to: Data final (padrão: hoje)
            page_size: Itens por página

        Returns:
            Lista de Transaction
        """
        if not date_from:
            date_from = date.today() - timedelta(days=90)
        if not date_to:
            date_to = date.today()

        # Resolver provider
        acc = await self._get(f"/accounts/{account_id}")
        item_data = await self._get(f"/items/{acc.get('itemId', '')}")
        provider = self._resolve_provider(item_data)

        transactions = []
        page = 1
        while True:
            data = await self._get("/transactions", params={
                "accountId": account_id,
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "pageSize": page_size,
                "page": page,
            })

            for tx in data.get("results", []):
                amount = Decimal(str(tx.get("amount", 0)))
                tx_type = self._classify_transaction(tx)

                transactions.append(Transaction(
                    id=tx.get("id", ""),
                    account_id=account_id,
                    provider=provider,
                    type=tx_type,
                    amount=abs(amount),
                    description=tx.get("description", ""),
                    date=self._parse_date(tx.get("date")) or datetime.now(),
                    category=tx.get("category"),
                    balance_after=Decimal(str(tx.get("balance", 0))) if tx.get("balance") is not None else None,
                    metadata={
                        "pluggy_id": tx.get("id"),
                        "status": tx.get("status"),
                        "payment_data": tx.get("paymentData"),
                        "credit_card_metadata": tx.get("creditCardMetadata"),
                    },
                ))

            total_pages = data.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1

        return sorted(transactions, key=lambda t: t.date, reverse=True)

    # ──────────── API: Cartão de Crédito ────────────

    async def get_credit_cards(self, bank: Optional[str] = None) -> List[CreditCard]:
        """
        Lista cartões de crédito.

        Returns:
            Lista de CreditCard
        """
        cards = []
        accounts = await self.get_accounts(bank)

        for acc in accounts:
            if acc.metadata.get("subtype") == "CREDIT_CARD" or acc.account_type == AccountType.PAGAMENTO:
                # Buscar dados detalhados da conta
                acc_data = await self._get(f"/accounts/{acc.id}")
                credit_data = acc_data.get("creditData") or {}

                raw_brand = credit_data.get("brand") or acc_data.get("marketingName", "")
                brand = self._resolve_brand(raw_brand)

                cards.append(CreditCard(
                    id=acc.id,
                    provider=acc.provider,
                    last_four_digits=acc_data.get("number", "")[-4:] if acc_data.get("number") else "****",
                    brand=brand,
                    holder_name=acc_data.get("owner", ""),
                    credit_limit=Decimal(str(credit_data.get("creditLimit", 0))),
                    available_limit=Decimal(str(credit_data.get("availableCreditLimit", 0))),
                    closing_day=credit_data.get("balanceCloseDate", 0) or 0,
                    due_day=credit_data.get("balanceDueDate", 0) or 0,
                    status="ACTIVE",
                ))

        return cards

    # ──────────── API: Faturas (Bills) ────────────

    async def get_bills(self, account_id: str) -> List[Invoice]:
        """
        Busca faturas do cartão de crédito.

        Args:
            account_id: ID da conta de cartão Pluggy

        Returns:
            Lista de Invoice
        """
        invoices = []
        try:
            data = await self._get(f"/accounts/{account_id}/bills")

            # Resolver provider
            acc = await self._get(f"/accounts/{account_id}")
            item_data = await self._get(f"/items/{acc.get('itemId', '')}")
            provider = self._resolve_provider(item_data)

            for bill in data.get("results", []):
                due_date_parsed = self._parse_date(bill.get("dueDate"))
                ref_date = self._parse_date(bill.get("closeDate") or bill.get("dueDate"))

                invoices.append(Invoice(
                    id=bill.get("id", ""),
                    card_id=account_id,
                    provider=provider,
                    reference_month=ref_date.strftime("%Y-%m") if ref_date else "",
                    total_amount=Decimal(str(bill.get("totalAmount", 0))),
                    minimum_payment=Decimal(str(bill.get("minimumPayment", 0))),
                    due_date=due_date_parsed.date() if due_date_parsed else date.today(),
                    status=bill.get("state", "OPEN").upper(),
                ))
        except PluggyConnectionError as e:
            logger.error(f"Erro ao buscar faturas: {e}")

        return sorted(invoices, key=lambda i: i.due_date, reverse=True)

    async def get_bill_transactions(
        self,
        account_id: str,
        bill_id: str,
    ) -> List[Transaction]:
        """
        Busca transações de uma fatura específica.

        Args:
            account_id: ID da conta de cartão Pluggy
            bill_id: ID da fatura

        Returns:
            Lista de Transaction da fatura
        """
        acc = await self._get(f"/accounts/{account_id}")
        item_data = await self._get(f"/items/{acc.get('itemId', '')}")
        provider = self._resolve_provider(item_data)

        transactions = []
        data = await self._get("/transactions", params={
            "accountId": account_id,
            "billId": bill_id,
            "pageSize": 500,
        })

        for tx in data.get("results", []):
            amount = Decimal(str(tx.get("amount", 0)))
            transactions.append(Transaction(
                id=tx.get("id", ""),
                account_id=account_id,
                provider=provider,
                type=TransactionType.CARD_PURCHASE,
                amount=abs(amount),
                description=tx.get("description", ""),
                date=self._parse_date(tx.get("date")) or datetime.now(),
                category=tx.get("category"),
                metadata={
                    "pluggy_id": tx.get("id"),
                    "installments": tx.get("creditCardMetadata", {}).get("totalInstallments")
                    if tx.get("creditCardMetadata") else None,
                    "installment_number": tx.get("creditCardMetadata", {}).get("installmentNumber")
                    if tx.get("creditCardMetadata") else None,
                },
            ))

        return sorted(transactions, key=lambda t: t.date, reverse=True)

    # ──────────── API: Identidade ────────────

    async def get_identity(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca dados de identidade do titular.

        Returns:
            Dict com nome, CPF (parcial), endereço, etc.
        """
        try:
            data = await self._get(f"/identity", params={"itemId": item_id})
            results = data.get("results", [])
            if results:
                identity = results[0]
                return {
                    "full_name": identity.get("fullName"),
                    "document": identity.get("document"),
                    "birth_date": identity.get("birthDate"),
                    "emails": identity.get("emails", []),
                    "phone_numbers": identity.get("phoneNumbers", []),
                }
        except PluggyConnectionError as e:
            logger.error(f"Erro ao buscar identidade: {e}")
        return None

    # ──────────── API: Investimentos ────────────

    async def get_investments(self, item_id: str) -> List[Dict[str, Any]]:
        """
        Busca investimentos vinculados a um item.

        Returns:
            Lista de dicts com dados de investimentos.
        """
        investments = []
        try:
            page = 1
            while True:
                data = await self._get("/investments", params={
                    "itemId": item_id,
                    "pageSize": 100,
                    "page": page,
                })
                for inv in data.get("results", []):
                    investments.append({
                        "id": inv.get("id"),
                        "name": inv.get("name"),
                        "type": inv.get("type"),
                        "subtype": inv.get("subtype"),
                        "balance": inv.get("balance"),
                        "amount_profit": inv.get("amountProfit"),
                        "amount_original": inv.get("amountOriginal"),
                        "currency": inv.get("currencyCode", "BRL"),
                        "rate": inv.get("rate"),
                        "rate_type": inv.get("rateType"),
                        "due_date": inv.get("dueDate"),
                        "issuer": inv.get("issuer"),
                        "last_updated": inv.get("lastUpdatedAt"),
                    })
                if page >= data.get("totalPages", 1):
                    break
                page += 1
        except PluggyConnectionError as e:
            logger.error(f"Erro ao buscar investimentos: {e}")

        return investments

    # ──────────── API: Empréstimos ────────────

    async def get_loans(self, item_id: str) -> List[Dict[str, Any]]:
        """
        Busca empréstimos vinculados a um item.

        Returns:
            Lista de dicts com dados de empréstimos.
        """
        loans = []
        try:
            data = await self._get("/loans", params={"itemId": item_id})
            for loan in data.get("results", []):
                loans.append({
                    "id": loan.get("id"),
                    "name": loan.get("name"),
                    "type": loan.get("type"),
                    "contract_number": loan.get("contractNumber"),
                    "principal": loan.get("principal"),
                    "outstanding_balance": loan.get("outstandingBalance"),
                    "monthly_payment": loan.get("monthlyPayment"),
                    "interest_rate": loan.get("interestRate"),
                    "installments_total": loan.get("numberOfInstallments"),
                    "installments_paid": loan.get("numberOfInstallmentsPaid"),
                    "due_date": loan.get("dueDate"),
                    "status": loan.get("status"),
                })
        except PluggyConnectionError as e:
            logger.error(f"Erro ao buscar empréstimos: {e}")

        return loans

    # ──────────── Métodos de conveniência ────────────

    async def get_nubank_card_statements(
        self,
        months_back: int = 3,
    ) -> Dict[str, Any]:
        """
        Busca extrato do cartão Nubank dos últimos N meses.

        Returns:
            Dict com faturas, transações e resumo.
        """
        item_id = self._get_item_id("nubank")

        # Buscar contas de cartão
        cards = await self.get_credit_cards("nubank")
        if not cards:
            return {"error": "Nenhum cartão Nubank encontrado", "cards": []}

        result = {
            "cards": [c.to_dict() for c in cards],
            "bills": [],
            "transactions": [],
            "summary": {},
        }

        for card in cards:
            # Buscar faturas
            bills = await self.get_bills(card.id)
            result["bills"].extend([b.to_dict() for b in bills])

            # Buscar transações dos últimos N meses
            date_from = date.today() - timedelta(days=30 * months_back)
            txs = await self.get_transactions(card.id, date_from=date_from)
            result["transactions"].extend([t.to_dict() for t in txs])

        # Resumo
        total = sum(Decimal(t["amount"]) for t in result["transactions"])
        result["summary"] = {
            "total_cards": len(cards),
            "total_bills": len(result["bills"]),
            "total_transactions": len(result["transactions"]),
            "total_amount": str(total),
            "period": f"Últimos {months_back} meses",
        }

        return result

    async def get_full_summary(self) -> Dict[str, Any]:
        """
        Resumo completo de todos os bancos conectados.

        Returns:
            Dict com contas, saldos, cartões e resumo geral.
        """
        summary = {
            "banks": {},
            "total_balance": Decimal("0"),
            "total_credit_limit": Decimal("0"),
            "total_credit_used": Decimal("0"),
        }

        for bank_name, item_id in self._item_ids.items():
            bank_data = {"accounts": [], "balances": [], "cards": [], "status": "OK"}

            try:
                # Status do item
                item = await self._get(f"/items/{item_id}")
                bank_data["connector"] = item.get("connector", {}).get("name")
                bank_data["last_updated"] = item.get("lastUpdatedAt")

                # Contas e saldos
                accounts = await self.get_accounts(bank_name)
                for acc in accounts:
                    bank_data["accounts"].append(acc.to_dict())
                    bal = await self.get_balance(acc.id)
                    if bal:
                        bank_data["balances"].append(bal.to_dict())
                        summary["total_balance"] += bal.available

                # Cartões
                cards = await self.get_credit_cards(bank_name)
                for card in cards:
                    bank_data["cards"].append(card.to_dict())
                    summary["total_credit_limit"] += card.credit_limit
                    summary["total_credit_used"] += card.used_limit

            except PluggyConnectionError as e:
                bank_data["status"] = "ERROR"
                bank_data["error"] = str(e)
                logger.error(f"Erro ao buscar dados de {bank_name}: {e}")

            summary["banks"][bank_name] = bank_data

        summary["total_balance"] = str(summary["total_balance"])
        summary["total_credit_limit"] = str(summary["total_credit_limit"])
        summary["total_credit_used"] = str(summary["total_credit_used"])

        return summary

    # ──────────── Configuração ────────────

    async def save_credentials(self):
        """Salva credenciais no vault Eddie."""
        self._security.store_credentials("pluggy", {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "item_ids": json.dumps(self._item_ids),
        })
        logger.info("Credenciais Pluggy salvas no vault")

    def add_item(self, bank_name: str, item_id: str):
        """Adiciona um item (banco) à lista de items."""
        self._item_ids[bank_name.lower()] = item_id
        logger.info(f"Item adicionado: {bank_name} → {item_id}")

    def remove_item(self, bank_name: str):
        """Remove um item da lista."""
        self._item_ids.pop(bank_name.lower(), None)
        logger.info(f"Item removido: {bank_name}")

    def __repr__(self) -> str:
        banks = ", ".join(self._item_ids.keys()) or "nenhum"
        configured = "✓" if self.is_configured else "✗"
        return f"PluggyConnector(configured={configured}, banks=[{banks}])"
