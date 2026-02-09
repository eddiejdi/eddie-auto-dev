"""
Conector Nubank — Open Finance Brasil + API interna.

Endpoints:
  - Autenticação OAuth2 (Open Finance)
  - Contas e saldos
  - Transações (conta e cartão)
  - Cartão de crédito (Nubank Roxinho)
  - PIX

Referência: https://open-banking.nubank.com.br/
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from .base_connector import BaseBankConnector, BankAuthError
from .models import (
    BankAccount, Balance, Transaction, PixKey, PixTransfer,
    CreditCard, Invoice, Consent, ConsentStatus,
    BankProvider, AccountType, TransactionType, PixKeyType, CardBrand,
)
from .security import BankingSecurityManager, OAuthToken
from .open_finance import (
    build_ofb_headers, build_consent_request, get_ofb_endpoint,
    OFB_API_VERSIONS, OFB_DEFAULT_PERMISSIONS,
)

logger = logging.getLogger("eddie.banking.nubank")


class NubankConnector(BaseBankConnector):
    """
    Conector para Nubank via Open Finance Brasil.

    Credenciais necessárias:
      BANK_NUBANK_CLIENT_ID
      BANK_NUBANK_CLIENT_SECRET

    O Nubank participa do Open Finance Brasil, portanto usa
    os mesmos padrões de consentimento e endpoints.

    Certificados mTLS:
      agent_data/banking/certs/nubank/client.pem
      agent_data/banking/certs/nubank/client.key
    """

    def __init__(
        self,
        security: Optional[BankingSecurityManager] = None,
        sandbox: bool = True,
    ):
        super().__init__(BankProvider.NUBANK, security, sandbox)
        self._base_url = get_ofb_endpoint("nubank", "base", sandbox)
        self._auth_url = get_ofb_endpoint("nubank", "auth", sandbox)

    # ──────────── Autenticação ────────────

    async def authenticate(self) -> Optional[OAuthToken]:
        """Autentica via OAuth2 client_credentials no Nubank."""
        creds = self.security.load_credentials("nubank")
        if not creds:
            raise BankAuthError("nubank", "Credenciais não encontradas. Configure BANK_NUBANK_CLIENT_ID/SECRET")

        data = {
            "grant_type": "client_credentials",
            "client_id": creds.get("client_id", ""),
            "client_secret": creds.get("client_secret", ""),
            "scope": "accounts balances transactions credit-cards-accounts consents payments",
        }

        resp = await self._request(
            "POST", f"{self._auth_url}/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            require_auth=False,
        )

        token = OAuthToken(
            access_token=resp["access_token"],
            token_type=resp.get("token_type", "Bearer"),
            expires_in=resp.get("expires_in", 3600),
            refresh_token=resp.get("refresh_token"),
        )
        self.security.cache_token("nubank", token)
        logger.info("Nubank: Autenticação bem-sucedida")
        return token

    async def authenticate_with_code(self, authorization_code: str) -> Optional[OAuthToken]:
        """Troca authorization_code por token (fluxo com consentimento)."""
        creds = self.security.load_credentials("nubank")
        if not creds:
            raise BankAuthError("nubank", "Credenciais não encontradas")

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": creds.get("redirect_uri", ""),
            "client_id": creds.get("client_id", ""),
            "client_secret": creds.get("client_secret", ""),
        }

        resp = await self._request(
            "POST", f"{self._auth_url}/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            require_auth=False,
        )

        token = OAuthToken(
            access_token=resp["access_token"],
            token_type=resp.get("token_type", "Bearer"),
            expires_in=resp.get("expires_in", 3600),
            refresh_token=resp.get("refresh_token"),
        )
        self.security.cache_token("nubank", token)
        return token

    # ──────────── Consentimento ────────────

    async def create_consent(self, permissions: Optional[List[str]] = None) -> Optional[Consent]:
        """Cria consentimento Open Finance no Nubank."""
        body = build_consent_request(permissions=permissions)
        version = OFB_API_VERSIONS["consents"]

        resp = await self._request(
            "POST",
            f"{self._base_url}/open-banking/consents/{version}/consents",
            json=body,
        )

        data = resp.get("data", {})
        return Consent(
            id=data.get("consentId", ""),
            provider=BankProvider.NUBANK,
            status=ConsentStatus(data.get("status", "AWAITING_AUTHORISATION")),
            permissions=data.get("permissions", []),
            expiration_datetime=datetime.fromisoformat(
                data.get("expirationDateTime", "").replace("Z", "+00:00")
            ) if data.get("expirationDateTime") else datetime.now(),
            redirect_url=data.get("links", {}).get("redirect"),
        )

    # ──────────── Contas ────────────

    async def get_accounts(self) -> List[BankAccount]:
        """Lista contas no Nubank (NuConta)."""
        version = OFB_API_VERSIONS["accounts"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/accounts/{version}/accounts"
        )

        accounts = []
        for item in resp.get("data", []):
            accounts.append(BankAccount(
                id=item.get("accountId", ""),
                provider=BankProvider.NUBANK,
                account_type=AccountType.PAGAMENTO,  # NuConta é conta de pagamento
                branch=item.get("branchCode", "0001"),
                number=item.get("number", ""),
                holder_name=item.get("companyCnpj", ""),
                holder_document=self.security.mask_document(item.get("companyCnpj", "")),
                currency="BRL",
            ))
        return accounts

    # ──────────── Saldo ────────────

    async def get_balance(self, account_id: str) -> Balance:
        """Obtém saldo da NuConta."""
        version = OFB_API_VERSIONS["balances"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/accounts/{version}/accounts/{account_id}/balances"
        )

        data = resp.get("data", [{}])
        bal = data[0] if isinstance(data, list) and data else data

        return Balance(
            account_id=account_id,
            provider=BankProvider.NUBANK,
            available=Decimal(str(bal.get("availableAmount", {}).get("amount", "0"))),
            blocked=Decimal(str(bal.get("blockedAmount", {}).get("amount", "0"))),
        )

    # ──────────── Transações ────────────

    async def get_transactions(
        self, account_id: str, start_date: date, end_date: date
    ) -> List[Transaction]:
        """Lista transações da NuConta."""
        version = OFB_API_VERSIONS["transactions"]
        params = {
            "fromBookingDate": start_date.isoformat(),
            "toBookingDate": end_date.isoformat(),
        }

        all_transactions: List[Transaction] = []
        url = f"{self._base_url}/open-banking/accounts/{version}/accounts/{account_id}/transactions"

        while url:
            resp = await self._request("GET", url, params=params)
            params = None

            for item in resp.get("data", []):
                credit_debit = item.get("creditDebitType", "DEBITO")
                tx_type = self._map_transaction_type(
                    item.get("type", ""), credit_debit
                )
                all_transactions.append(Transaction(
                    id=item.get("transactionId", self._generate_id()),
                    account_id=account_id,
                    provider=BankProvider.NUBANK,
                    type=tx_type,
                    amount=Decimal(str(item.get("amount", "0"))),
                    description=item.get("transactionName", ""),
                    date=datetime.fromisoformat(
                        item.get("transactionDateTime", item.get("bookingDate", "")).replace("Z", "+00:00")
                    ),
                    counterpart_name=item.get("creditorAccount", {}).get("name"),
                    reference=item.get("transactionId"),
                ))

            next_link = resp.get("links", {}).get("next")
            url = next_link if next_link else None

        return all_transactions

    # ──────────── Cartão Nubank ────────────

    async def get_credit_cards(self) -> List[CreditCard]:
        """Lista cartões de crédito Nubank (Roxinho)."""
        version = OFB_API_VERSIONS["credit_cards"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/credit-cards-accounts/{version}/accounts"
        )

        cards = []
        for item in resp.get("data", []):
            limits = item.get("lineLimitUsed", [{}])
            limit_data = limits[0] if limits else {}

            cards.append(CreditCard(
                id=item.get("creditCardAccountId", ""),
                provider=BankProvider.NUBANK,
                last_four_digits=item.get("number", "")[-4:] if item.get("number") else "****",
                brand=CardBrand.MASTERCARD,  # Nubank usa Mastercard
                holder_name=item.get("name", ""),
                credit_limit=Decimal(str(limit_data.get("lineLimit", {}).get("amount", "0"))),
                available_limit=Decimal(str(limit_data.get("availableAmount", {}).get("amount", "0"))),
                closing_day=int(item.get("paymentMethod", {}).get("identifiers", [{}])[0].get("number", "3")) if item.get("paymentMethod") else 3,
                due_day=int(item.get("paymentMethod", {}).get("identifiers", [{}])[0].get("number", "10")) if item.get("paymentMethod") else 10,
            ))
        return cards

    async def get_invoice(self, card_id: str, reference_month: str) -> Optional[Invoice]:
        """Obtém fatura do cartão Nubank."""
        version = OFB_API_VERSIONS["credit_cards"]
        resp = await self._request(
            "GET",
            f"{self._base_url}/open-banking/credit-cards-accounts/{version}/accounts/{card_id}/bills",
        )

        for bill in resp.get("data", []):
            bill_date = bill.get("dueDate", "")
            if bill_date.startswith(reference_month):
                return Invoice(
                    id=bill.get("billId", ""),
                    card_id=card_id,
                    provider=BankProvider.NUBANK,
                    reference_month=reference_month,
                    total_amount=Decimal(str(bill.get("billTotalAmount", {}).get("amount", "0"))),
                    minimum_payment=Decimal(str(bill.get("billMinimumAmount", {}).get("amount", "0"))),
                    due_date=date.fromisoformat(bill_date[:10]) if bill_date else date.today(),
                    status="CLOSED" if bill.get("isInstalment") else "OPEN",
                )
        return None

    # ──────────── Helpers ────────────

    @staticmethod
    def _map_transaction_type(tx_type: str, credit_debit: str) -> TransactionType:
        mapping = {
            "PIX": TransactionType.PIX_SENT if credit_debit == "DEBITO" else TransactionType.PIX_RECEIVED,
            "TED": TransactionType.TED_SENT if credit_debit == "DEBITO" else TransactionType.TED_RECEIVED,
            "BOLETO": TransactionType.BOLETO_PAYMENT,
            "TARIFA": TransactionType.FEE,
        }
        if tx_type.upper() in mapping:
            return mapping[tx_type.upper()]
        return TransactionType.CREDIT if credit_debit == "CREDITO" else TransactionType.DEBIT
