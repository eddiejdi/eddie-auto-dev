"""
Conector Base para integrações bancárias.
Todos os conectores (Santander, Itaú, Nubank, Mercado Pago) herdam desta classe.
"""

import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

import httpx

from .models import (
    BankAccount, Balance, Transaction, PixKey, PixTransfer,
    BankStatement, CreditCard, Invoice, Consent, BankProvider,
)
from .security import BankingSecurityManager, OAuthToken

logger = logging.getLogger("eddie.banking")


class BankConnectionError(Exception):
    """Erro de conexão com o banco."""
    def __init__(self, provider: str, message: str, status_code: Optional[int] = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message} (HTTP {status_code})" if status_code else f"[{provider}] {message}")


class BankAuthError(BankConnectionError):
    """Erro de autenticação / autorização."""
    pass


class BankRateLimitError(BankConnectionError):
    """Rate limit excedido."""
    pass


class BaseBankConnector(ABC):
    """
    Classe base abstrata para conectores bancários.

    Subclasses devem implementar:
      - authenticate()
      - get_accounts()
      - get_balance(account_id)
      - get_transactions(account_id, start_date, end_date)

    Opcionalmente:
      - get_pix_keys(account_id)
      - initiate_pix(transfer)
      - get_credit_cards()
      - get_invoice(card_id, month)
      - create_consent(permissions)
    """

    def __init__(
        self,
        provider: BankProvider,
        security: Optional[BankingSecurityManager] = None,
        sandbox: bool = True,
        timeout: int = 30,
    ):
        self.provider = provider
        self.security = security or BankingSecurityManager()
        self.sandbox = sandbox
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[OAuthToken] = None
        self._retry_count = 3
        self._retry_delay = 1.0

    # ──────────── HTTP Client ────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna httpx client com configuração mTLS se disponível."""
        if self._client is None or self._client.is_closed:
            kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "follow_redirects": True,
                "headers": {"User-Agent": "Eddie-Banking-Agent/1.0"},
            }
            # mTLS para Open Finance
            cert_paths = self.security.get_cert_paths(self.provider.value)
            if cert_paths:
                kwargs["cert"] = (cert_paths["cert"], cert_paths["key"])
                if "ca" in cert_paths:
                    kwargs["verify"] = cert_paths["ca"]

            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def close(self):
        """Fecha conexão HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ──────────── Request com retry ────────────

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        require_auth: bool = True,
    ) -> Dict[str, Any]:
        """
        Faz request HTTP com retry automático e tratamento de erros bancários.
        """
        client = await self._get_client()

        # Garantir autenticação
        if require_auth:
            token = self.security.get_cached_token(self.provider.value)
            if not token:
                token = await self.authenticate()
            if not token:
                raise BankAuthError(self.provider.value, "Falha na autenticação")
            self._token = token
            headers = headers or {}
            headers["Authorization"] = token.authorization_header

        last_error = None
        for attempt in range(1, self._retry_count + 1):
            try:
                resp = await client.request(
                    method, url, headers=headers, json=json, params=params, data=data
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", self._retry_delay * attempt))
                    logger.warning(f"[{self.provider.value}] Rate limit, aguardando {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 401:
                    # Token expirado, tentar renovar
                    self.security.invalidate_token(self.provider.value)
                    token = await self.authenticate()
                    if token and headers:
                        headers["Authorization"] = token.authorization_header
                        continue
                    raise BankAuthError(self.provider.value, "Token expirado e renovação falhou", 401)

                if resp.status_code == 403:
                    raise BankAuthError(self.provider.value, "Acesso negado (consent?)", 403)

                if resp.status_code >= 500:
                    logger.warning(f"[{self.provider.value}] Erro servidor {resp.status_code}, tentativa {attempt}/{self._retry_count}")
                    await asyncio.sleep(self._retry_delay * attempt)
                    continue

                resp.raise_for_status()
                return resp.json() if resp.content else {}

            except httpx.TimeoutException:
                last_error = BankConnectionError(self.provider.value, f"Timeout ({self.timeout}s)")
                logger.warning(f"[{self.provider.value}] Timeout, tentativa {attempt}/{self._retry_count}")
                await asyncio.sleep(self._retry_delay * attempt)
            except httpx.ConnectError as e:
                last_error = BankConnectionError(self.provider.value, f"Conexão falhou: {e}")
                await asyncio.sleep(self._retry_delay * attempt)
            except (BankAuthError, BankRateLimitError):
                raise
            except httpx.HTTPStatusError as e:
                raise BankConnectionError(
                    self.provider.value,
                    f"HTTP Error: {e.response.text[:200]}",
                    e.response.status_code,
                )

        raise last_error or BankConnectionError(self.provider.value, "Máximo de retries excedido")

    # ──────────── Abstract Methods ────────────

    @abstractmethod
    async def authenticate(self) -> Optional[OAuthToken]:
        """Autentica com o banco e retorna token OAuth2."""
        ...

    @abstractmethod
    async def get_accounts(self) -> List[BankAccount]:
        """Lista contas bancárias do usuário."""
        ...

    @abstractmethod
    async def get_balance(self, account_id: str) -> Balance:
        """Obtém saldo de uma conta."""
        ...

    @abstractmethod
    async def get_transactions(
        self, account_id: str, start_date: date, end_date: date
    ) -> List[Transaction]:
        """Lista transações de uma conta em um período."""
        ...

    # ──────────── Métodos opcionais (implementação padrão retorna vazio) ────────────

    async def get_pix_keys(self, account_id: str) -> List[PixKey]:
        """Lista chaves PIX vinculadas a uma conta."""
        return []

    async def initiate_pix(self, transfer: PixTransfer) -> PixTransfer:
        """Inicia transferência PIX."""
        raise NotImplementedError(f"{self.provider.value} não suporta PIX via API")

    async def get_credit_cards(self) -> List[CreditCard]:
        """Lista cartões de crédito."""
        return []

    async def get_invoice(self, card_id: str, reference_month: str) -> Optional[Invoice]:
        """Obtém fatura do cartão."""
        return None

    async def get_statement(
        self, account_id: str, start_date: date, end_date: date
    ) -> BankStatement:
        """Gera extrato consolidado. Implementação padrão usa get_balance + get_transactions."""
        balance = await self.get_balance(account_id)
        transactions = await self.get_transactions(account_id, start_date, end_date)

        # Calcular saldo de abertura a partir do saldo atual e transações
        total_movement = sum(
            t.amount if t.is_credit else -t.amount for t in transactions
        )
        opening = balance.available - total_movement

        return BankStatement(
            account_id=account_id,
            provider=self.provider,
            start_date=start_date,
            end_date=end_date,
            opening_balance=opening,
            closing_balance=balance.available,
            transactions=sorted(transactions, key=lambda t: t.date),
        )

    async def create_consent(self, permissions: Optional[List[str]] = None) -> Optional[Consent]:
        """Cria consentimento Open Finance."""
        return None

    async def get_consent_status(self, consent_id: str) -> Optional[Consent]:
        """Verifica status do consentimento."""
        return None

    # ──────────── Helpers ────────────

    def _generate_id(self) -> str:
        """Gera ID único para transações e requests."""
        return str(uuid.uuid4())

    @property
    def provider_name(self) -> str:
        return self.provider.value.title()

    def __repr__(self) -> str:
        mode = "sandbox" if self.sandbox else "production"
        return f"<{self.__class__.__name__} provider={self.provider.value} mode={mode}>"
