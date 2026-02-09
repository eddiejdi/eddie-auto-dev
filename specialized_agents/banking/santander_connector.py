"""
Conector Santander Brasil — Open Finance Brasil.

Endpoints:
  - Autenticação OAuth2 (client_credentials + authorization_code)
  - Contas e saldos
  - Transações / Extrato
  - Cartões de crédito e faturas
  - PIX (iniciação de pagamentos)

Referência: https://developer.santander.com.br/
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

logger = logging.getLogger("eddie.banking.santander")


class SantanderConnector(BaseBankConnector):
    """
    Conector para Santander Brasil via Open Finance.

    Credenciais necessárias (env ou vault):
      BANK_SANTANDER_CLIENT_ID
      BANK_SANTANDER_CLIENT_SECRET
      BANK_SANTANDER_REDIRECT_URI

    Certificados mTLS em:
      agent_data/banking/certs/santander/client.pem
      agent_data/banking/certs/santander/client.key
    """

    def __init__(
        self,
        security: Optional[BankingSecurityManager] = None,
        sandbox: bool = True,
    ):
        super().__init__(BankProvider.SANTANDER, security, sandbox)
        self._base_url = get_ofb_endpoint("santander", "base", sandbox)
        self._auth_url = get_ofb_endpoint("santander", "auth", sandbox)

    # ──────────── Autenticação ────────────

    async def authenticate(self) -> Optional[OAuthToken]:
        """
        Autentica via OAuth2 client_credentials.
        Para fluxo completo com usuário, usar authenticate_with_code().
        """
        creds = self.security.load_credentials("santander")
        if not creds:
            raise BankAuthError("santander", "Credenciais não encontradas. Configure BANK_SANTANDER_CLIENT_ID/SECRET")

        client_id = creds.get("client_id", "")
        client_secret = creds.get("client_secret", "")

        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
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
            scope=resp.get("scope"),
        )
        self.security.cache_token("santander", token)
        logger.info("Santander: Autenticação bem-sucedida")
        return token

    async def authenticate_with_code(self, authorization_code: str) -> Optional[OAuthToken]:
        """Troca authorization_code por access_token (fluxo com consentimento do usuário)."""
        creds = self.security.load_credentials("santander")
        if not creds:
            raise BankAuthError("santander", "Credenciais não encontradas")

        code_verifier = creds.get("code_verifier", "")
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": creds.get("redirect_uri", ""),
            "client_id": creds.get("client_id", ""),
            "client_secret": creds.get("client_secret", ""),
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

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
            scope=resp.get("scope"),
        )
        self.security.cache_token("santander", token)
        return token

    # ──────────── Consentimento ────────────

    async def create_consent(self, permissions: Optional[List[str]] = None) -> Optional[Consent]:
        """Cria consentimento Open Finance no Santander."""
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
            provider=BankProvider.SANTANDER,
            status=ConsentStatus(data.get("status", "AWAITING_AUTHORISATION")),
            permissions=data.get("permissions", []),
            expiration_datetime=datetime.fromisoformat(
                data.get("expirationDateTime", "").replace("Z", "+00:00")
            ) if data.get("expirationDateTime") else datetime.now(),
            redirect_url=data.get("links", {}).get("redirect"),
        )

    # ──────────── Contas ────────────

    async def get_accounts(self) -> List[BankAccount]:
        """Lista contas do usuário no Santander."""
        version = OFB_API_VERSIONS["accounts"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/accounts/{version}/accounts"
        )

        accounts = []
        for item in resp.get("data", []):
            acc_type_map = {
                "CONTA_DEPOSITO_A_VISTA": AccountType.CONTA_CORRENTE,
                "CONTA_POUPANCA": AccountType.POUPANCA,
                "CONTA_PAGAMENTO_PRE_PAGA": AccountType.PAGAMENTO,
            }
            accounts.append(BankAccount(
                id=item.get("accountId", ""),
                provider=BankProvider.SANTANDER,
                account_type=acc_type_map.get(item.get("type", ""), AccountType.CONTA_CORRENTE),
                branch=item.get("branchCode", ""),
                number=item.get("number", ""),
                holder_name=item.get("companyCnpj", item.get("compeCode", "")),
                holder_document=self.security.mask_document(item.get("companyCnpj", "")),
                currency=item.get("currency", "BRL"),
            ))
        return accounts

    # ──────────── Saldo ────────────

    async def get_balance(self, account_id: str) -> Balance:
        """Obtém saldo da conta no Santander."""
        version = OFB_API_VERSIONS["balances"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/accounts/{version}/accounts/{account_id}/balances"
        )

        data = resp.get("data", [{}])
        bal = data[0] if isinstance(data, list) and data else data

        return Balance(
            account_id=account_id,
            provider=BankProvider.SANTANDER,
            available=Decimal(str(bal.get("availableAmount", {}).get("amount", "0"))),
            blocked=Decimal(str(bal.get("blockedAmount", {}).get("amount", "0"))),
            overdraft_limit=Decimal(str(bal.get("overdraftContractedLimit", {}).get("amount", "0"))),
        )

    # ──────────── Transações ────────────

    async def get_transactions(
        self, account_id: str, start_date: date, end_date: date
    ) -> List[Transaction]:
        """Lista transações da conta no Santander."""
        version = OFB_API_VERSIONS["transactions"]
        params = {
            "fromBookingDate": start_date.isoformat(),
            "toBookingDate": end_date.isoformat(),
        }

        all_transactions: List[Transaction] = []
        url = f"{self._base_url}/open-banking/accounts/{version}/accounts/{account_id}/transactions"

        while url:
            resp = await self._request("GET", url, params=params)
            params = None  # Params só na primeira request

            for item in resp.get("data", []):
                tx_type = self._map_transaction_type(item.get("type", ""), item.get("creditDebitType", ""))
                all_transactions.append(Transaction(
                    id=item.get("transactionId", self._generate_id()),
                    account_id=account_id,
                    provider=BankProvider.SANTANDER,
                    type=tx_type,
                    amount=Decimal(str(item.get("amount", "0"))),
                    description=item.get("transactionName", item.get("completedAuthorisedPaymentType", "")),
                    date=datetime.fromisoformat(item.get("transactionDateTime", item.get("bookingDate", "")).replace("Z", "+00:00")),
                    counterpart_name=item.get("creditorAccount", {}).get("name"),
                    reference=item.get("transactionId"),
                ))

            # Paginação
            next_link = resp.get("links", {}).get("next")
            url = next_link if next_link else None

        return all_transactions

    # ──────────── Cartões ────────────

    async def get_credit_cards(self) -> List[CreditCard]:
        """Lista cartões de crédito no Santander."""
        version = OFB_API_VERSIONS["credit_cards"]
        resp = await self._request(
            "GET", f"{self._base_url}/open-banking/credit-cards-accounts/{version}/accounts"
        )

        cards = []
        for item in resp.get("data", []):
            brand_map = {"VISA": CardBrand.VISA, "MASTERCARD": CardBrand.MASTERCARD, "ELO": CardBrand.ELO}
            cards.append(CreditCard(
                id=item.get("creditCardAccountId", ""),
                provider=BankProvider.SANTANDER,
                last_four_digits=item.get("number", "")[-4:] if item.get("number") else "****",
                brand=brand_map.get(item.get("productType", "").upper(), CardBrand.OTHER),
                holder_name=item.get("name", ""),
                credit_limit=Decimal(str(item.get("lineLimitUsed", [{}])[0].get("lineLimit", {}).get("amount", "0"))) if item.get("lineLimitUsed") else Decimal("0"),
                available_limit=Decimal(str(item.get("lineLimitUsed", [{}])[0].get("availableAmount", {}).get("amount", "0"))) if item.get("lineLimitUsed") else Decimal("0"),
                closing_day=int(item.get("paymentMethod", {}).get("identifiers", [{}])[0].get("number", "1")) if item.get("paymentMethod") else 1,
                due_day=int(item.get("paymentMethod", {}).get("identifiers", [{}])[0].get("number", "10")) if item.get("paymentMethod") else 10,
            ))
        return cards

    # ──────────── Helpers ────────────

    @staticmethod
    def _map_transaction_type(tx_type: str, credit_debit: str) -> TransactionType:
        """Mapeia tipo de transação Open Finance para TransactionType."""
        mapping = {
            "PIX": TransactionType.PIX_SENT if credit_debit == "DEBITO" else TransactionType.PIX_RECEIVED,
            "TED": TransactionType.TED_SENT if credit_debit == "DEBITO" else TransactionType.TED_RECEIVED,
            "BOLETO": TransactionType.BOLETO_PAYMENT,
            "TARIFA": TransactionType.FEE,
            "IMPOSTO": TransactionType.TAX,
        }
        if tx_type.upper() in mapping:
            return mapping[tx_type.upper()]
        if credit_debit == "CREDITO":
            return TransactionType.CREDIT
        return TransactionType.DEBIT
