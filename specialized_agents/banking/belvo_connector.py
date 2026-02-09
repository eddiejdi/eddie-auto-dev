"""
Conector Belvo — Agregador Open Finance Brasil.

Usa a API da Belvo (https://belvo.com) como intermediário para
acessar dados de Santander, Itaú e Nubank, sem necessidade de
registro direto como ITP/ITD no BCB.

Fluxo:
  1. Cadastre-se em https://dashboard.belvo.com/signup/ → obtenha SECRET_ID e SECRET_PASSWORD
  2. Use o Connect Widget (ou API) para o usuário vincular seus bancos → cria Link
  3. Com o link_id, busque accounts, balances, transactions, bills

Variáveis de ambiente:
  BELVO_SECRET_ID        — ID de autenticação Belvo
  BELVO_SECRET_PASSWORD  — Senha de autenticação Belvo
  BELVO_ENV              — "sandbox" (padrão) ou "production"

Documentação: https://developers.belvo.com/reference/using-our-api
"""

import os
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

import httpx

from .models import (
    BankAccount, Balance, Transaction, CreditCard, Invoice,
    BankStatement, BankProvider, AccountType, TransactionType, CardBrand,
)
from .security import BankingSecurityManager

logger = logging.getLogger("eddie.banking.belvo")

# ──────────── Mapeamento de instituições Belvo → BankProvider ────────────

BELVO_INSTITUTION_MAP = {
    # Open Finance Brasil (OFDA)
    "santander_br_ofda": BankProvider.SANTANDER,
    "itau_br_ofda": BankProvider.ITAU,
    "nubank_br_ofda": BankProvider.NUBANK,
    # Nomes alternativos
    "erebancobrasil_br_ofda": BankProvider.ITAU,
    "nu_br_ofda": BankProvider.NUBANK,
    "santanderof_br_ofda": BankProvider.SANTANDER,
}

# Inverso: BankProvider → nome de instituição preferido Belvo
PROVIDER_TO_BELVO = {
    BankProvider.SANTANDER: "santander_br_ofda",
    BankProvider.ITAU: "itau_br_ofda",
    BankProvider.NUBANK: "nubank_br_ofda",
}

# Map Belvo account types → nosso AccountType
BELVO_ACCOUNT_TYPE_MAP = {
    "CHECKING": AccountType.CONTA_CORRENTE,
    "SAVINGS": AccountType.POUPANCA,
    "PAYMENT": AccountType.PAGAMENTO,
    "SALARY": AccountType.SALARIO,
    "CONTA_DEPOSITO_A_VISTA": AccountType.CONTA_CORRENTE,
    "CONTA_POUPANCA": AccountType.POUPANCA,
    "CONTA_PAGAMENTO_PRE_PAGA": AccountType.PAGAMENTO,
}


class BelvoConnectionError(Exception):
    """Erro de conexão com Belvo API."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(f"[Belvo] {message}" + (f" (HTTP {status_code})" if status_code else ""))


class BelvoConnector:
    """
    Conector unificado via Belvo para bancos brasileiros Open Finance.

    Gerencia múltiplos links (Santander, Itaú, Nubank) através de uma
    única API, eliminando a necessidade de certificados mTLS e registro ITP.
    """

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_password: Optional[str] = None,
        environment: Optional[str] = None,
        security: Optional[BankingSecurityManager] = None,
    ):
        self.secret_id = secret_id or os.getenv("BELVO_SECRET_ID", "")
        self.secret_password = secret_password or os.getenv("BELVO_SECRET_PASSWORD", "")
        self.environment = environment or os.getenv("BELVO_ENV", "sandbox")
        self.security = security or BankingSecurityManager()

        self.base_url = (
            "https://api.belvo.com"
            if self.environment == "production"
            else "https://sandbox.belvo.com"
        )

        # Cache de links e contas
        self._links: Dict[str, Dict[str, Any]] = {}  # link_id → {institution, status, ...}
        self._link_by_provider: Dict[BankProvider, str] = {}  # provider → link_id
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Retorna True se as credenciais Belvo estão definidas."""
        return bool(self.secret_id and self.secret_password)

    # ──────────── HTTP Client ────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.secret_id, self.secret_password),
                timeout=httpx.Timeout(30.0),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Any:
        """Executa request com retry e tratamento de erros."""
        client = await self._get_client()

        for attempt in range(3):
            try:
                response = await client.request(
                    method, path, json=json_data, params=params
                )

                if response.status_code == 401:
                    raise BelvoConnectionError("Credenciais inválidas", 401)
                if response.status_code == 404:
                    return None
                if response.status_code == 429:
                    import asyncio
                    wait = 2 ** attempt
                    logger.warning(f"Rate limit Belvo, aguardando {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                if response.status_code >= 500:
                    import asyncio
                    wait = 3 * (2 ** attempt)
                    logger.warning(f"Belvo 5xx ({response.status_code}), retry em {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if attempt == 2:
                    raise BelvoConnectionError(str(e), e.response.status_code)
            except httpx.RequestError as e:
                if attempt == 2:
                    raise BelvoConnectionError(f"Erro de rede: {e}")

        raise BelvoConnectionError("Máximo de tentativas excedido")

    # ──────────── Widget Token ────────────

    async def create_widget_token(
        self,
        widget_branding: Optional[Dict] = None,
        institution_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Gera token para o Belvo Connect Widget (frontend).

        O widget permite que o usuário vincule suas contas bancárias
        de forma segura, sem expor credenciais para nosso backend.

        Returns:
            {"access": "eyJ...", "refresh": "eyJ...", "link": null}
        """
        payload: Dict[str, Any] = {
            "id": self.secret_id,
            "password": self.secret_password,
        }

        if widget_branding:
            payload["widget"] = {"branding": widget_branding}

        # Filtrar para Brasil Open Finance
        if institution_types:
            payload["scopes"] = ",".join(institution_types)

        result = await self._request("POST", "/api/token/", json_data=payload)
        logger.info("Widget token gerado com sucesso")
        return result

    # ──────────── Links (conexões bancárias) ────────────

    async def list_links(self) -> List[Dict[str, Any]]:
        """Lista todos os links (conexões bancárias) criados."""
        result = await self._request("GET", "/api/links/")
        links = result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

        self._links.clear()
        self._link_by_provider.clear()
        for link in links:
            link_id = link.get("id", "")
            institution = link.get("institution", "")
            self._links[link_id] = link

            # Mapear para BankProvider
            provider = BELVO_INSTITUTION_MAP.get(institution)
            if provider:
                self._link_by_provider[provider] = link_id

        return links

    async def create_link(
        self,
        institution: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        external_id: Optional[str] = None,
        access_mode: str = "recurrent",
    ) -> Dict[str, Any]:
        """
        Cria um link (conexão) com uma instituição bancária.

        Para Open Finance Brasil, o username/password NÃO são necessários —
        o fluxo de consentimento é tratado pelo widget/redirect.

        Args:
            institution: Nome da instituição (ex: "santander_br_ofda")
            username: Usuário (opcional para OFB)
            password: Senha (opcional para OFB)
            external_id: ID externo para tracking
            access_mode: "single" ou "recurrent"
        """
        payload: Dict[str, Any] = {
            "institution": institution,
            "access_mode": access_mode,
        }
        if username:
            payload["username"] = username
        if password:
            payload["password"] = password
        if external_id:
            payload["external_id"] = external_id

        result = await self._request("POST", "/api/links/", json_data=payload)
        link_id = result.get("id", "")
        self._links[link_id] = result

        provider = BELVO_INSTITUTION_MAP.get(institution)
        if provider:
            self._link_by_provider[provider] = link_id

        logger.info(f"Link criado: {institution} → {link_id}")
        return result

    async def refresh_link(self, link_id: str) -> Dict[str, Any]:
        """Atualiza/refresca um link existente."""
        result = await self._request("POST", f"/api/links/{link_id}/refresh/")
        if result:
            self._links[link_id] = result
        return result

    async def get_link(self, link_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de um link específico."""
        return await self._request("GET", f"/api/links/{link_id}/")

    async def delete_link(self, link_id: str):
        """Remove um link (desconecta do banco)."""
        await self._request("DELETE", f"/api/links/{link_id}/")
        self._links.pop(link_id, None)
        # Remover do mapa de providers
        self._link_by_provider = {k: v for k, v in self._link_by_provider.items() if v != link_id}

    def get_link_for_provider(self, provider: BankProvider) -> Optional[str]:
        """Retorna link_id vinculado a um banco específico."""
        return self._link_by_provider.get(provider)

    # ──────────── Institutions ────────────

    async def list_institutions(self, country: str = "BR") -> List[Dict[str, Any]]:
        """Lista instituições disponíveis (filtrado por país)."""
        params = {"country_code": country, "page_size": 100}
        result = await self._request("GET", "/api/institutions/", params=params)
        return result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

    # ──────────── Consents (Open Finance Brasil) ────────────

    async def list_consents(self, link_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista consentimentos Open Finance."""
        params = {}
        if link_id:
            params["link"] = link_id
        result = await self._request("GET", "/api/consents/", params=params)
        return result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

    # ──────────── Owners ────────────

    async def get_owner(self, link_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações do titular da conta."""
        result = await self._request(
            "POST", "/api/owners/", json_data={"link": link_id}
        )
        if isinstance(result, list) and result:
            return result[0]
        return result

    # ──────────── Accounts ────────────

    async def retrieve_accounts(self, link_id: str) -> List[Dict[str, Any]]:
        """Busca e armazena contas de um link no Belvo."""
        result = await self._request(
            "POST", "/api/accounts/",
            json_data={"link": link_id}
        )
        return result if isinstance(result, list) else [result] if result else []

    async def list_accounts(self, link_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista contas já armazenadas."""
        params = {}
        if link_id:
            params["link"] = link_id
        result = await self._request("GET", "/api/accounts/", params=params)
        return result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

    def _to_bank_account(self, belvo_account: Dict, provider: BankProvider) -> BankAccount:
        """Converte conta Belvo → nosso modelo BankAccount."""
        raw_type = belvo_account.get("type", "CHECKING")
        account_type = BELVO_ACCOUNT_TYPE_MAP.get(raw_type, AccountType.CONTA_CORRENTE)

        return BankAccount(
            id=belvo_account.get("id", ""),
            provider=provider,
            account_type=account_type,
            branch=belvo_account.get("agency", belvo_account.get("branch", "0001")),
            number=belvo_account.get("number", belvo_account.get("internal_identification", "")),
            holder_name=belvo_account.get("name", belvo_account.get("holder_name", "")),
            holder_document=self.security.mask_document(belvo_account.get("holder_document", "")),
            currency=belvo_account.get("currency", "BRL"),
            status="ACTIVE" if belvo_account.get("status") != "CLOSED" else "CLOSED",
            metadata={
                "belvo_id": belvo_account.get("id"),
                "institution": belvo_account.get("institution", {}).get("name", ""),
                "category": belvo_account.get("category", ""),
            },
        )

    # ──────────── Balances (Brazil) ────────────

    async def retrieve_balances(
        self, link_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Busca saldos de um link (endpoint Brasil)."""
        payload: Dict[str, Any] = {"link": link_id}
        if date_from:
            payload["date_from"] = date_from
        if date_to:
            payload["date_to"] = date_to

        result = await self._request("POST", "/api/br/balances/", json_data=payload)
        return result if isinstance(result, list) else [result] if result else []

    async def list_balances(self, link_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista saldos já armazenados."""
        params = {}
        if link_id:
            params["link"] = link_id
        result = await self._request("GET", "/api/br/balances/", params=params)
        return result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

    def _to_balance(self, belvo_balance: Dict, account_id: str, provider: BankProvider) -> Balance:
        """Converte saldo Belvo → nosso modelo Balance."""
        return Balance(
            account_id=account_id,
            provider=provider,
            available=Decimal(str(belvo_balance.get("current_balance", 0))),
            blocked=Decimal(str(belvo_balance.get("blocked_balance", 0))),
            currency=belvo_balance.get("currency", "BRL"),
            timestamp=datetime.fromisoformat(belvo_balance["collected_at"])
            if belvo_balance.get("collected_at")
            else datetime.now(),
        )

    # ──────────── Transactions ────────────

    async def retrieve_transactions(
        self,
        link_id: str,
        date_from: str,
        date_to: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Busca transações de um link no período especificado."""
        payload: Dict[str, Any] = {
            "link": link_id,
            "date_from": date_from,
        }
        if date_to:
            payload["date_to"] = date_to
        if account_id:
            payload["account"] = account_id

        result = await self._request("POST", "/api/transactions/", json_data=payload)
        return result if isinstance(result, list) else [result] if result else []

    async def list_transactions(
        self,
        link_id: Optional[str] = None,
        account_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista transações já armazenadas (com filtros)."""
        params: Dict[str, str] = {}
        if link_id:
            params["link"] = link_id
        if account_id:
            params["account"] = account_id
        if date_from:
            params["value_date__gte"] = date_from
        if date_to:
            params["value_date__lte"] = date_to

        all_results = []
        page = 1
        while True:
            params["page"] = str(page)
            result = await self._request("GET", "/api/transactions/", params=params)
            if isinstance(result, dict):
                items = result.get("results", [])
                all_results.extend(items)
                if not result.get("next"):
                    break
                page += 1
            else:
                break

        return all_results

    def _to_transaction(self, belvo_tx: Dict, provider: BankProvider) -> Transaction:
        """Converte transação Belvo → nosso modelo Transaction."""
        raw_type = belvo_tx.get("type", "")
        amount = Decimal(str(belvo_tx.get("amount", 0)))
        description = belvo_tx.get("description", "") or ""

        # Determinar tipo de transação
        tx_type = self._classify_transaction(raw_type, amount, description)

        return Transaction(
            id=belvo_tx.get("id", ""),
            account_id=belvo_tx.get("account", {}).get("id", "") if isinstance(belvo_tx.get("account"), dict) else belvo_tx.get("account", ""),
            provider=provider,
            type=tx_type,
            amount=abs(amount),
            description=description,
            category=belvo_tx.get("category", ""),
            date=datetime.fromisoformat(belvo_tx["value_date"]).date()
            if belvo_tx.get("value_date")
            else date.today(),
            balance_after=Decimal(str(belvo_tx.get("balance", 0))) if belvo_tx.get("balance") else None,
            counterpart_name=belvo_tx.get("merchant", {}).get("name", "") if isinstance(belvo_tx.get("merchant"), dict) else "",
            metadata={
                "belvo_id": belvo_tx.get("id"),
                "reference": belvo_tx.get("reference", ""),
                "status": belvo_tx.get("status", ""),
                "subcategory": belvo_tx.get("subcategory", ""),
            },
        )

    def _classify_transaction(self, raw_type: str, amount: Decimal, desc: str) -> TransactionType:
        """Classifica tipo de transação baseado nos dados Belvo."""
        desc_lower = desc.lower()

        if "pix" in desc_lower:
            return TransactionType.PIX_RECEIVED if amount > 0 else TransactionType.PIX_SENT
        if "ted" in desc_lower:
            return TransactionType.TED_RECEIVED if amount > 0 else TransactionType.TED_SENT
        if "boleto" in desc_lower:
            return TransactionType.BOLETO_PAYMENT
        if "tarifa" in desc_lower or "taxa" in desc_lower:
            return TransactionType.FEE
        if "juros" in desc_lower:
            return TransactionType.INTEREST
        if "salario" in desc_lower or "salário" in desc_lower:
            return TransactionType.SALARY
        if "estorno" in desc_lower:
            return TransactionType.REFUND
        if raw_type == "OUTFLOW" or amount < 0:
            return TransactionType.DEBIT
        if raw_type == "INFLOW" or amount > 0:
            return TransactionType.CREDIT

        return TransactionType.OTHER

    # ──────────── Bills (faturas cartão) ────────────

    async def retrieve_bills(self, link_id: str) -> List[Dict[str, Any]]:
        """Busca faturas de cartão de crédito."""
        result = await self._request(
            "POST", "/api/bills/",
            json_data={"link": link_id}
        )
        return result if isinstance(result, list) else [result] if result else []

    async def list_bills(self, link_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista faturas já armazenadas."""
        params = {}
        if link_id:
            params["link"] = link_id
        result = await self._request("GET", "/api/bills/", params=params)
        return result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []

    # ──────────── Investments (Brasil) ────────────

    async def retrieve_investments(self, link_id: str) -> List[Dict[str, Any]]:
        """Busca dados de investimentos do link."""
        result = await self._request(
            "POST", "/api/br/investments/",
            json_data={"link": link_id}
        )
        return result if isinstance(result, list) else [result] if result else []

    # ──────────── Métodos de alto nível ────────────

    async def get_all_accounts(self) -> List[BankAccount]:
        """Busca contas de todos os links conectados em formato padronizado."""
        await self.list_links()  # Atualiza cache
        accounts = []

        for provider, link_id in self._link_by_provider.items():
            try:
                raw_accounts = await self.list_accounts(link_id)
                if not raw_accounts:
                    raw_accounts = await self.retrieve_accounts(link_id)

                for acc in raw_accounts:
                    accounts.append(self._to_bank_account(acc, provider))
            except Exception as e:
                logger.error(f"Erro ao buscar contas {provider.value}: {e}")

        return accounts

    async def get_all_balances(self) -> List[Balance]:
        """Busca saldos de todos os links conectados."""
        await self.list_links()
        balances = []

        for provider, link_id in self._link_by_provider.items():
            try:
                raw_balances = await self.list_balances(link_id)
                if not raw_balances:
                    raw_balances = await self.retrieve_balances(link_id)

                for bal in raw_balances:
                    account_id = bal.get("account", {}).get("id", "") if isinstance(bal.get("account"), dict) else bal.get("account", "")
                    balances.append(self._to_balance(bal, account_id, provider))
            except Exception as e:
                logger.error(f"Erro ao buscar saldos {provider.value}: {e}")

        return balances

    async def get_all_transactions(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Transaction]:
        """Busca transações de todos os links conectados."""
        await self.list_links()

        if not date_from:
            date_from = date.today().replace(day=1).isoformat()
        if not date_to:
            date_to = date.today().isoformat()

        transactions = []
        for provider, link_id in self._link_by_provider.items():
            try:
                raw_txs = await self.list_transactions(
                    link_id=link_id, date_from=date_from, date_to=date_to
                )
                if not raw_txs:
                    raw_txs = await self.retrieve_transactions(link_id, date_from, date_to)

                for tx in raw_txs:
                    transactions.append(self._to_transaction(tx, provider))
            except Exception as e:
                logger.error(f"Erro ao buscar transações {provider.value}: {e}")

        return sorted(transactions, key=lambda t: t.date, reverse=True)

    async def get_connected_banks(self) -> Dict[BankProvider, Dict[str, Any]]:
        """Retorna mapa de bancos conectados com status."""
        links = await self.list_links()
        result = {}

        for link in links:
            institution = link.get("institution", "")
            provider = BELVO_INSTITUTION_MAP.get(institution)
            if provider:
                result[provider] = {
                    "link_id": link.get("id"),
                    "institution": institution,
                    "status": link.get("status", "unknown"),
                    "access_mode": link.get("access_mode", ""),
                    "created_at": link.get("created_at", ""),
                    "last_accessed_at": link.get("last_accessed_at", ""),
                }

        return result

    # ──────────── Health check ────────────

    async def health_check(self) -> Dict[str, Any]:
        """Verifica conectividade e status de cada link."""
        status = {
            "belvo_configured": self.is_configured,
            "environment": self.environment,
            "banks": {},
        }

        if not self.is_configured:
            status["error"] = "Credenciais Belvo não configuradas"
            return status

        try:
            banks = await self.get_connected_banks()
            for provider, info in banks.items():
                status["banks"][provider.value] = {
                    "connected": info["status"] in ("valid", "active"),
                    "status": info["status"],
                    "last_access": info.get("last_accessed_at"),
                }
            status["total_connected"] = len(banks)
        except Exception as e:
            status["error"] = str(e)

        return status


# ──────────── Singleton ────────────

_belvo_connector: Optional[BelvoConnector] = None


def get_belvo_connector() -> BelvoConnector:
    """Retorna instância singleton do conector Belvo."""
    global _belvo_connector
    if _belvo_connector is None:
        _belvo_connector = BelvoConnector()
    return _belvo_connector
